import math
from unittest import TestCase

from core.spur_measurement import measure_visible_spur


class VisibleSpurMeasurementTests(TestCase):
    def test_curved_length_follows_the_outline_between_supplied_endpoints(self):
        angles=[i*math.pi/40 for i in range(21)]
        outline=[[100+66*math.cos(a),100+66*math.sin(a)] for a in angles]
        outline += [[100+54*math.cos(a),100+54*math.sin(a)] for a in reversed(angles)]
        result=measure_visible_spur(outline,[160,100],[100,160],220,220,10)
        self.assertGreater(result['length_px'],math.dist([160,100],[100,160]))
        self.assertAlmostEqual(result['length_px'],60*math.pi/2,delta=12)
        self.assertEqual(result['centerline'][0],[160,100])
        self.assertEqual(result['centerline'][-1],[100,160])
        self.assertAlmostEqual(result['physical_length_cm'],result['length_px']/10,delta=.002)

    def test_missing_or_outside_endpoints_are_not_invented(self):
        polygon=[[10,10],[80,10],[80,30],[10,30]]
        for base,tip in ((None,[70,20]),([20,20],None),([0,0],[70,20]),([20,20],[20,20])):
            with self.assertRaises(ValueError):measure_visible_spur(polygon,base,tip,100,100)

    def test_invalid_geometry_and_calibration_are_rejected(self):
        for polygon in ([[10,10],[80,80],[10,80],[80,10]],[[1,1],[2,2],[3,3]],[[False,10],[80,10],[20,30]]):
            with self.assertRaises(ValueError):measure_visible_spur(polygon,[20,20],[70,20],100,100)
        for scale in (-1,0,float('nan'),'invalid'):
            with self.assertRaises(ValueError):measure_visible_spur([[10,10],[80,10],[80,30],[10,30]],[20,20],[70,20],100,100,scale)

    def test_scale_is_required_and_frame_truncation_blocks_complete_centimeters(self):
        shape=[[0,10],[80,10],[80,30],[0,30]]
        result=measure_visible_spur(shape,[2,20],[70,20],100,100,10)
        self.assertTrue(result['truncated_at_frame'])
        self.assertIsNone(result['physical_length_cm'])
        result=measure_visible_spur([[10,10],[80,10],[80,30],[10,30]],[20,20],[70,20],100,100)
        self.assertIsNone(result['physical_length_cm'])
