/* LagLens SVG line chart. Uniform time bins, explicit axes, no smoothed values.
 * Small enough for a student to read and maintain the complete rendering path.
 */
window.Charts={
  line(element,options){
    const NS='http://www.w3.org/2000/svg';
    const make=(tag,attrs,parent,text)=>{
      const node=document.createElementNS(NS,tag);
      for(const [key,value]of Object.entries(attrs||{}))node.setAttribute(key,value);
      if(text!==undefined)node.textContent=text;
      parent?.append(node);return node;
    };
    element.replaceChildren();
    const width=Math.max(element.clientWidth,240),height=options.height||220;
    const data=options.series[0].values,labels=options.labels;
    const values=data.filter(v=>v!==null&&Number.isFinite(v));
    const maxValue=Math.max(options.max||0,...values,1);
    const rawStep=maxValue/4,magnitude=10**Math.floor(Math.log10(rawStep));
    const step=[1,2,2.5,5,10].map(n=>n*magnitude).find(n=>n>=rawStep)||10*magnitude;
    const upper=Math.ceil(maxValue/step)*step;
    const left=44,right=12,top=options.annotations?.length||options.reference?32:14,bottom=30;
    const plotWidth=width-left-right,plotHeight=height-top-bottom;
    const x=i=>left+plotWidth*i/Math.max(data.length-1,1);
    const y=value=>top+plotHeight*(1-value/upper);
    const style=getComputedStyle(element),colour=name=>style.getPropertyValue(name).trim();
    const svg=make('svg',{viewBox:`0 0 ${width} ${height}`,width:'100%',height,role:'img','aria-label':'Presented frame time in milliseconds over capture time'},element);
    make('title',{},svg,'Frame-time peaks are preserved within equal-width time bins.');
    for(let tick=0;tick<=upper+step/2;tick+=step){
      const coordinate=y(tick);
      make('line',{x1:left,y1:coordinate,x2:width-right,y2:coordinate,stroke:colour('--grid'),'stroke-width':1},svg);
      make('text',{x:left-9,y:coordinate+4,'text-anchor':'end',fill:colour('--muted'),'font-size':11},svg,options.tickFormat?options.tickFormat(tick):tick.toFixed(0));
    }
    const picks=width<400?[0,Math.floor((data.length-1)/2),data.length-1]:options.xAt||[0,data.length-1];
    for(const index of [...new Set(picks)]){
      make('text',{x:x(index),y:height-6,fill:colour('--muted'),'font-size':11,'text-anchor':index===0?'start':index===data.length-1?'end':'middle'},svg,labels[index]||'');
    }
    if(options.reference){
      const reference=options.reference;
      make('line',{x1:left,y1:y(reference.value),x2:width-right,y2:y(reference.value),stroke:colour('--muted'),'stroke-width':1,'stroke-dasharray':'4 5'},svg);
      make('text',{x:left,y:14,fill:colour('--muted'),'font-size':11},svg,reference.label);
    }
    let path='',connected=false;
    data.forEach((value,index)=>{
      if(value===null||!Number.isFinite(value)){connected=false;return;}
      path+=`${connected?'L':'M'}${x(index).toFixed(2)},${y(value).toFixed(2)} `;
      connected=true;
    });
    make('path',{d:path,stroke:colour('--chart-1'),'stroke-width':1.7,fill:'none','stroke-linejoin':'round'},svg);
    for(const annotation of options.annotations||[]){
      const xpos=x(annotation.at),label=width<400?annotation.short:annotation.label;
      make('line',{x1:xpos,y1:26,x2:xpos,y2:height-bottom,stroke:colour('--chart-2'),'stroke-width':1,'stroke-dasharray':'2 4',opacity:.75},svg);
      make('text',{x:width-right,y:14,'text-anchor':'end',fill:colour('--text'),'font-size':11},svg,label);
    }
    const cursor=make('line',{x1:0,y1:top,x2:0,y2:height-bottom,stroke:colour('--muted'),opacity:0},svg);
    const hint=make('text',{x:width-right,y:height-bottom-9,'text-anchor':'end',fill:colour('--text'),'font-size':12},svg,'');
    svg.addEventListener('pointermove',event=>{
      const bounds=svg.getBoundingClientRect();
      const index=Math.max(0,Math.min(data.length-1,Math.round(((event.clientX-bounds.left)/bounds.width*width-left)/plotWidth*(data.length-1))));
      cursor.setAttribute('x1',x(index));cursor.setAttribute('x2',x(index));cursor.setAttribute('opacity',.6);
      hint.textContent=`${labels[index]} · ${data[index]===null?'No frame in this bin':options.format(data[index])}`;
    });
    svg.addEventListener('pointerleave',()=>{cursor.setAttribute('opacity',0);hint.textContent='';});
  }
};
