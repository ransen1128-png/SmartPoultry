document.addEventListener('DOMContentLoaded', () => {
    const editor = document.querySelector('.spur-review-editor');
    if (!editor) return;
    const width = Number(editor.dataset.width), height = Number(editor.dataset.height);
    const initial = JSON.parse(document.getElementById('spur-review-initial').textContent);
    const state = {polygon: initial.polygon || [], base: initial.base || null, tip: initial.tip || null};
    const svg = document.getElementById('spurReviewCanvas'), shapes = document.getElementById('spurReviewShapes');
    const status = document.getElementById('spurReviewStatus'), confirmation = document.getElementById('spurReviewConfirmation');
    let tool = 'polygon';
    const add = (tag, attributes, text) => {
        const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
        Object.entries(attributes).forEach(([key,value]) => node.setAttribute(key,value));
        if (text) node.textContent = text;
        shapes.appendChild(node);
    };
    const draw = () => {
        shapes.replaceChildren();
        add(state.polygon.length >= 3 ? 'polygon' : 'polyline', {points: state.polygon.map(p => p.join(',')).join(' '), fill: '#9c27b0', 'fill-opacity': .2, stroke: '#9c27b0', 'stroke-width': 2, 'vector-effect': 'non-scaling-stroke'});
        for (const [name,color] of [['base','#07853d'],['tip','#d32f2f']]) {
            const p = state[name];
            if (!p) continue;
            add('circle',{cx:p[0],cy:p[1],r:Math.max(2,width/120),fill:color,stroke:'#fff','stroke-width':1,'vector-effect':'non-scaling-stroke'});
            add('text',{x:p[0]+width/70,y:p[1],fill:color,'font-size':Math.max(12,width/35),stroke:'#fff','stroke-width':.5,'paint-order':'stroke'},name === 'base' ? 'Base' : 'Tip');
        }
        status.textContent = `Tool: ${tool}. Outline: ${state.polygon.length} points. Base: ${state.base ? 'marked' : 'not marked'}. Tip: ${state.tip ? 'marked' : 'not marked'}.`;
        document.getElementById('spurReviewData').value = JSON.stringify(state);
    };
    document.querySelectorAll('[data-review-tool]').forEach(button => button.addEventListener('click', () => {tool=button.dataset.reviewTool;draw();}));
    svg.addEventListener('pointerdown', event => {
        const matrix=svg.getScreenCTM();
        if (!matrix) return;
        const point=new DOMPoint(event.clientX,event.clientY).matrixTransform(matrix.inverse());
        const p=[Math.round(Math.max(0,Math.min(width-1,point.x))*100)/100,Math.round(Math.max(0,Math.min(height-1,point.y))*100)/100];
        if (tool==='polygon') {
            if (state.polygon.length>=240) {status.textContent='The outline limit is 240 points.';return;}
            state.polygon.push(p);
        } else state[tool]=p;
        confirmation.checked=false;draw();
    });
    document.getElementById('spurReviewUndo').addEventListener('click',()=>{state.polygon.pop();confirmation.checked=false;draw();});
    document.getElementById('spurReviewReset').addEventListener('click',()=>{state.polygon=[];state.base=null;state.tip=null;confirmation.checked=false;draw();});
    document.getElementById('spurReviewForm').addEventListener('submit',event=>{
        if (state.polygon.length<3 || !state.base || !state.tip) {event.preventDefault();status.textContent='Trace the outline, then mark the visible base and tip before saving.';}
    });
    draw();
});
