"""Measure a visible outline between explicit base/tip points, never from a box."""
import math

import numpy as np
from PIL import Image, ImageDraw


def _point(value, width, height):
    if (not isinstance(value, (list, tuple)) or len(value) != 2
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in value)
            or not 0 <= value[0] <= width-1 or not 0 <= value[1] <= height-1):
        raise ValueError('Mark a valid, visible base and tip inside the photograph.')
    return [float(v) for v in value]


def _cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def _on_segment(point, a, b):
    return (abs(_cross(a,b,point)) < 1e-7
            and min(a[0],b[0])-1e-7 <= point[0] <= max(a[0],b[0])+1e-7
            and min(a[1],b[1])-1e-7 <= point[1] <= max(a[1],b[1])+1e-7)


def _intersects(a, b, c, d):
    x, y, z, w = _cross(a,b,c), _cross(a,b,d), _cross(c,d,a), _cross(c,d,b)
    return ((x*y < 0 and z*w < 0) or _on_segment(c,a,b) or _on_segment(d,a,b)
            or _on_segment(a,c,d) or _on_segment(b,c,d))


def contains_point(point, polygon):
    inside = False
    for a, b in zip(polygon, polygon[1:]+polygon[:1]):
        if _on_segment(point,a,b):
            return True
        if (a[1] > point[1]) != (b[1] > point[1]):
            crossing = (b[0]-a[0])*(point[1]-a[1])/(b[1]-a[1])+a[0]
            if point[0] < crossing:
                inside = not inside
    return inside


def validate_outline(polygon, width, height):
    if not isinstance(polygon, list) or not 3 <= len(polygon) <= 240:
        raise ValueError('Trace the visible spur outline using 3 to 240 points.')
    points = []
    for value in polygon:
        point = _point(value,width,height)
        if not points or point != points[-1]:
            points.append(point)
    if len(points)>1 and points[0]==points[-1]:
        points.pop()
    if len(points)<3:
        raise ValueError('The outline needs at least three distinct points.')
    area=abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:]+points[:1])))/2
    if area<1:
        raise ValueError('The visible outline has no measurable area.')
    for i in range(len(points)):
        for j in range(i+1,len(points)):
            if j==i+1 or (i==0 and j==len(points)-1):
                continue
            if _intersects(points[i],points[(i+1)%len(points)],points[j],points[(j+1)%len(points)]):
                raise ValueError('Outline edges must not cross or touch themselves.')
    return points


def measure_visible_spur(polygon, base, tip, width, height, pixels_per_cm=None, *, source='user_reviewed'):
    from scipy.ndimage import distance_transform_edt
    from skimage.graph import route_through_array
    from skimage.morphology import skeletonize

    if width<=0 or height<=0 or width*height>16_000_000:
        raise ValueError('This image is too large for the measurement editor.')
    points=validate_outline(polygon,width,height)
    base,tip=_point(base,width,height),_point(tip,width,height)
    if math.dist(base,tip)<1:
        raise ValueError('Base and tip must be different visible points.')
    if not contains_point(base,points) or not contains_point(tip,points):
        raise ValueError('Base and tip must lie on or inside the traced spur outline.')
    if pixels_per_cm is not None:
        try:pixels_per_cm=float(pixels_per_cm)
        except (ValueError,TypeError):raise ValueError('Image scale must be positive and finite.')
        if not math.isfinite(pixels_per_cm) or pixels_per_cm<=0:
            raise ValueError('Image scale must be positive and finite.')
    x1,y1=np.floor(np.min(points,axis=0)).astype(int)
    x2,y2=np.ceil(np.max(points,axis=0)).astype(int)
    factor=min(1.,1020/max(x2-x1+1,y2-y1+1))
    canvas=Image.new('1',(max(3,math.ceil((x2-x1+1)*factor)+3),max(3,math.ceil((y2-y1+1)*factor)+3)))
    ImageDraw.Draw(canvas).polygon([((x-x1)*factor+1,(y-y1)*factor+1) for x,y in points],fill=1)
    binary=np.array(canvas.convert('L'),dtype=np.uint8)>0
    if binary.sum()<3:
        raise ValueError('The visible outline is too small to measure.')
    skeleton=skeletonize(binary)
    cost=1+4*distance_transform_edt(~skeleton)
    cost[~binary]=np.inf

    def raster_point(point):
        x,y=round((point[0]-x1)*factor+1),round((point[1]-y1)*factor+1)
        choices=[(math.hypot(dx,dy),y+dy,x+dx) for dy in range(-2,3) for dx in range(-2,3)
                 if 0<=y+dy<binary.shape[0] and 0<=x+dx<binary.shape[1] and binary[y+dy,x+dx]]
        if not choices:
            raise ValueError('An endpoint could not be placed on the visible mask.')
        _,y,x=min(choices);return (y,x)

    try:path,_=route_through_array(cost,raster_point(base),raster_point(tip),fully_connected=True,geometric=True)
    except ValueError:raise ValueError('The outline does not connect the visible base and tip.')
    full=[base]+[[(x-1)/factor+x1,(y-1)/factor+y1] for y,x in path]+[tip]
    length=sum(math.dist(a,b) for a,b in zip(full,full[1:]))
    truncated=any(x<=1 or y<=1 or x>=width-2 or y>=height-2 for x,y in points)
    sampled=full[::max(1,math.ceil(len(full)/240))]
    if sampled[-1]!=tip:sampled.append(tip)
    result={'source':source,'status':'reviewed_visible_projected_length','polygon':points,'base':base,'tip':tip,
            'length_px':round(length,2),'centerline':[[round(x,2),round(y,2)] for x,y in sampled],
            'physical_length_cm':None,'truncated_at_frame':truncated,'pixel_path_resolution_scale':factor,
            'method':'Mask-constrained centerline between explicitly marked base and tip',
            'limitation':'Projected visible image length; perspective, annotation and pixel resolution affect the result. This is not a verified 3D anatomical length.'}
    if pixels_per_cm is not None and not truncated:
        result['physical_length_cm']=round(length/pixels_per_cm,3)
        result['calibration']={'pixels_per_cm':pixels_per_cm,'source':'user_supplied_known_in_plane_scale'}
    return result
