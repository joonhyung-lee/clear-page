/* Local scroll state only; section navigation adds no network requests. */
(() => {
 const rail=document.querySelector('#section-rail');if(!rail)return;
 const links=[...rail.querySelectorAll('a')];
 const sections=links.map(a=>document.getElementById(a.hash.slice(1)));
 let queued=false;
 function update(){
  queued=false;let index=0;
  sections.forEach((section,i)=>{if(section.getBoundingClientRect().top<=Math.max(150,innerHeight*.33))index=i;});
  links.forEach((link,i)=>{if(i===index)link.setAttribute('aria-current','location');else link.removeAttribute('aria-current');});
 }
 addEventListener('scroll',()=>{if(!queued){queued=true;requestAnimationFrame(update);}},{passive:true});
 addEventListener('resize',update);update();
})();
