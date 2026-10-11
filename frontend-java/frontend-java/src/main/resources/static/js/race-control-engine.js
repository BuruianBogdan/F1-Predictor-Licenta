/* Frame-rate independent replay clock and bounded interpolation of measured positions. */
((scope)=>{
  const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
  class Clock {
    constructor(now=()=>performance.now()){this.now=now;this.start=0;this.end=Infinity;this.at=0;this.anchor=now();this.speed=1;this.playing=false;}
    value(){return clamp(this.at+(this.playing?(this.now()-this.anchor)/1000*this.speed:0),this.start,this.end);}
    configure(start,end,at=start){this.start=start;this.end=end;this.at=clamp(at,start,end);this.anchor=this.now();}
    seek(at){this.at=clamp(at,this.start,this.end);this.anchor=this.now();}
    play(){this.seek(this.value());this.playing=true;}
    pause(){this.seek(this.value());this.playing=false;}
    setSpeed(speed){this.seek(this.value());this.speed=clamp(Number(speed)||1,.25,30);}
    syncLive(at){this.seek(this.playing?Math.max(this.value(),at):at);this.speed=1;this.playing=true;}
  }
  function slope(a,b,c,axis){const d1=(b[axis]-a[axis])/(b[0]-a[0]),d2=(c[axis]-b[axis])/(c[0]-b[0]);return d1*d2<=0?0:2*d1*d2/(d1+d2);}
  function samplePosition(points,at){
    if(!points?.length||at<points[0][0])return null;
    let lo=0,hi=points.length;while(lo<hi){const m=(lo+hi)>>1;if(points[m][0]<=at)lo=m+1;else hi=m;}
    const i=lo-1,a=points[i],b=points[i+1],age=Math.max(0,at-a[0]);
    if(!b||b[0]-a[0]>3)return {x:a[1],y:a[2],age,stale:age>2.5,measuredAt:a[0],interpolated:false};
    const dt=b[0]-a[0],u=clamp((at-a[0])/dt,0,1),out=[];
    for(let axis=1;axis<=2;axis++){
      const sec=(b[axis]-a[axis])/dt,prev=points[i-1],next=points[i+2];
      const m0=prev&&a[0]-prev[0]<3?slope(prev,a,b,axis):sec;
      const m1=next&&next[0]-b[0]<3?slope(a,b,next,axis):sec;
      const v=(2*u**3-3*u**2+1)*a[axis]+(u**3-2*u**2+u)*dt*m0+(-2*u**3+3*u**2)*b[axis]+(u**3-u**2)*dt*m1;
      out.push(clamp(v,Math.min(a[axis],b[axis]),Math.max(a[axis],b[axis])));
    }
    return {x:out[0],y:out[1],age:0,stale:false,measuredAt:a[0],interpolated:true};
  }
  function horizon(speed){return clamp(Math.ceil(speed*7+15),30,240);}
  function layoutLabels(cars,width=800,height=460){
    const result=new Map();
    // Each chip belongs to its dot. Neighbours and timing order never move it.
    for(const car of cars){
      const w=car.selected?82:48,h=22,ux=car.direction?.[0]||0,uy=car.direction?.[1]||0;
      const x=clamp(car.x-w/2+8*ux,8,width-w-8),y=clamp(car.y-38+8*uy,8,height-h-8);
      result.set(car.number,{x,y,w,h,dx:x-car.x,dy:y-car.y});
    }
    return result;
  }
  const ns='http://www.w3.org/2000/svg';
  function svg(tag,attrs={}){const el=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))el.setAttribute(k,v);return el;}
  class MapRenderer {
    constructor(map,onSelect){this.map=map;this.onSelect=onSelect;this.nodes=new Map();this.positions=new Map();this.track=null;this.frame=null;this.selected=null;this.pathKey='';}
    reset(){for(const id of ['car-markers','car-labels','car-trails','car-label-stems','track-sectors','track-landmarks'])document.getElementById(id)?.replaceChildren();this.nodes.clear();this.positions.clear();this.frame=null;this.pathKey='';}
    project(x,y){const [x0,y0,x1,y1]=this.track.bounds,s=Math.min(680/(x1-x0),350/(y1-y0));return [400+(x-(x0+x1)/2)*s,230-(y-(y0+y1)/2)*s];}
    setFrame(frame,selected){this.frame=frame;this.selected=selected;if(!frame.track)return;this.track=frame.track;this.map.dataset.flag=frame.flag;
      const key=`${frame.meta.session_key}/${frame.track.driver_number}/${frame.track.lap}/${frame.track.landmarks_version||0}/${frame.track.pit_lane?.points.length||0}`;
      if(key!==this.pathKey){this.pathKey=key;const path=frame.track.points.map((p,i)=>{const [x,y]=this.project(...p);return `${i?'L':'M'}${x.toFixed(2)},${y.toFixed(2)}`;}).join(' ')+' Z';for(const id of ['track-road','track-halo','track-path']){const el=document.getElementById(id);el?.setAttribute('d',path);el?.removeAttribute('transform');}
        const group=document.getElementById('track-sectors');group?.replaceChildren();for(const s of frame.track.sectors||[]){const [x,y]=this.project(s.x,s.y),g=svg('g',{'class':'rc-sector-marker',transform:`translate(${x} ${y})`});g.append(svg('circle',{r:4}));const t=svg('text',{x:8,y:4});t.textContent=`S${s.sector}`;g.append(t);group?.append(g);}this.landmarks();}
    }
    landmarks(){
      const group=document.getElementById('track-landmarks');group?.replaceChildren();
      const pit=this.track.pit_lane,start=this.track.start_finish;
      if(pit){const path=pit.points.map((p,i)=>{const [x,y]=this.project(...p);return `${i?'L':'M'}${x.toFixed(2)},${y.toFixed(2)}`;}).join(' ');
        group?.append(svg('path',{'class':'rc-pit-road',d:path}),svg('path',{'class':'rc-pit-path',d:path}));
        for(const [name,point] of [['PIT IN',pit.entry],['PIT OUT',pit.exit]]){const [x,y]=this.project(...point),g=svg('g',{'class':'rc-pit-marker',transform:`translate(${x} ${y})`});g.append(svg('circle',{r:3.5}));const t=svg('text',{x:-9,y:18,'text-anchor':'end'});t.textContent=name;g.append(t);group?.append(g);}
      }
      if(start){const [x,y]=this.project(start.x,start.y),angle=Math.atan2(-start.direction[1],start.direction[0])*180/Math.PI;
        const g=svg('g',{'class':'rc-start-line',transform:`translate(${x} ${y})`}),line=svg('g',{transform:`rotate(${angle})`});line.append(svg('rect',{x:-3,y:-10,width:6,height:20,fill:'url(#start-checkers)'}));g.append(line);
        const t=svg('text',{x:14,y:4});t.textContent='START / FINISH';g.append(t);const title=svg('title');title.textContent='Approximate timing line from measured flying-lap positions';g.append(title);group?.append(g);
      }
      const note=document.getElementById('map-landmarks-note');if(note)note.textContent=pit?'Start / finish and pit lane follow measured trajectories; landmarks are approximate.':'Pit-lane geometry is unavailable in this feed; no route is invented.';
    }
    ensure(driver){let node=this.nodes.get(driver.driver_number);if(node)return node;const id=driver.driver_number,g=svg('g',{'class':'rc-car','data-driver':id,'tabindex':0,'role':'button','aria-label':`Follow ${driver.name}`});const ring=svg('circle',{'class':'rc-car-ring',r:13}),dot=svg('circle',{'class':'rc-car-dot',r:6,fill:driver.color}),heading=svg('path',{'class':'rc-car-direction',d:'M9 0 L4 -3 L4 3 Z',fill:driver.color});const title=svg('title');title.textContent=driver.name;g.append(ring,dot,heading,title);g.addEventListener('click',()=>this.onSelect(id));g.addEventListener('keydown',e=>{if(e.key==='Enter')this.onSelect(id);});document.getElementById('car-markers').append(g);
      const label=svg('g',{'class':'rc-driver-label','data-driver':id,tabindex:0,role:'button','aria-label':`Follow ${driver.name}`});const rect=svg('rect',{width:48,height:22,rx:5});const bar=svg('rect',{width:3,height:16,x:3,y:3,rx:1,fill:driver.color});const text=svg('text',{x:11,y:15});label.append(rect,bar,text);label.addEventListener('click',()=>this.onSelect(id));label.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();this.onSelect(id);}});document.getElementById('car-labels').append(label);const trail=svg('path',{'class':'rc-car-trail',stroke:driver.color});document.getElementById('car-trails').append(trail);const stem=svg('path',{'class':'rc-label-stem'});document.getElementById('car-label-stems').append(stem);node={g,ring,dot,heading,label,text,rect,trail,stem,direction:[0,0]};this.nodes.set(id,node);return node;
    }
    draw(at,now){if(!this.frame||!this.track)return;const cars=[];let stale=0,visible=0;
      for(const driver of this.frame.rows){const node=this.ensure(driver),points=this.frame.locations[String(driver.driver_number)]||[],p=samplePosition(points,at),selected=driver.driver_number===this.selected;
        if(!p){node.g.style.display='none';node.label.style.display='none';node.trail.style.display='none';node.stem.style.display='none';continue;}
        const [x,y]=this.project(p.x,p.y);if(x<-25||x>825||y<-25||y>485){node.g.style.display='none';node.label.style.display='none';node.trail.style.display='none';node.stem.style.display='none';continue;}
        visible++;if(p.stale)stale++;node.g.style.display='';node.label.style.display='';node.g.classList.toggle('selected',selected);node.g.classList.toggle('stale',p.stale);node.g.classList.toggle('incident',!!driver.condition?.body_alert);node.g.setAttribute('transform',`translate(${x.toFixed(3)} ${y.toFixed(3)})`);node.ring.style.display=selected||p.stale?'':'none';node.label.classList.toggle('selected',selected);node.label.classList.toggle('stale',p.stale);node.rect.setAttribute('width',selected?82:48);node.text.textContent=selected?`${driver.code}  P${driver.position||'—'}`:driver.code;
        const next=samplePosition(points,at+.2);if(next&&!next.stale){const xy=this.project(next.x,next.y);const angle=Math.atan2(xy[1]-y,xy[0]-x)*180/Math.PI;node.heading.setAttribute('transform',`rotate(${angle})`);}const moved=next?Math.hypot(next.x-p.x,next.y-p.y):0;node.heading.style.display=selected&&!p.stale&&moved>1?'':'none';node.g.querySelector('title').textContent=`${driver.name} · ${p.stale?'delayed position; last sample '+p.age.toFixed(1)+'s ago':moved<1?'position unchanged in current measurements':'measured position'}${driver.in_pit?' · PIT':''}`;
        node.trail.style.display=selected&&!p.stale?'':'none';if(selected){const history=points.filter(v=>v[0]>=at-2&&v[0]<=at).map(v=>this.project(v[1],v[2]));history.push([x,y]);node.trail.setAttribute('d',history.map((v,i)=>`${i?'L':'M'}${v[0].toFixed(2)},${v[1].toFixed(2)}`).join(' '));}
        const before=samplePosition(points,at-.8),after=samplePosition(points,at+.8);
        if(!p.stale&&before&&!before.stale&&after&&!after.stale){const a=this.project(before.x,before.y),b=this.project(after.x,after.y),length=Math.hypot(b[0]-a[0],b[1]-a[1]);if(length>.6)node.direction=[(b[0]-a[0])/length,(b[1]-a[1])/length];}
        cars.push({x,y,number:driver.driver_number,selected,direction:node.direction});this.positions.set(driver.driver_number,{x,y});
      }
      const labels=layoutLabels(cars);
      for(const car of cars){const node=this.nodes.get(car.number),box=labels.get(car.number);node.label.setAttribute('transform',`translate(${box.x.toFixed(3)} ${box.y.toFixed(3)})`);node.stem.style.display='';node.stem.setAttribute('d',`M${car.x.toFixed(3)} ${(car.y-7).toFixed(3)} L${(box.x+box.w/2).toFixed(3)} ${(box.y+box.h).toFixed(3)}`);}
      const status=document.getElementById('position-status');if(status)status.textContent=`${visible-stale} fresh · ${stale} delayed`;
    }
  }
  const api={Clock,samplePosition,horizon,layoutLabels,MapRenderer};scope.RaceControlEngine=api;if(typeof module!=='undefined')module.exports=api;
})(globalThis);
