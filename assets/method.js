/* Paper equations, with descriptive underbraces on the combined objective. */
(() => {
 const fonts=new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting)){
  fonts.disconnect();loadScript('assets/math-fonts.js',()=>!!window.CLEAR_MATH_FONTS).catch(()=>{});
 }},{rootMargin:'200px'});
 document.querySelectorAll('[data-tex]').forEach(el=>fonts.observe(el));
 document.querySelectorAll('[data-tex]').forEach(el => {
  let tex=el.dataset.tex;
  if(el.dataset.objectiveAnnotations){
   const terms=[
    [String.raw`\mathcal{L}_{\mathrm{order}}`,'Selection / rank','order'],
    [String.raw`\lambda_{\mathrm{flow}}\mathcal{L}_{\mathrm{flow}}`,'Generation','flow'],
    [String.raw`\lambda_{\mathrm{aff}}\mathcal{L}_{\mathrm{aff}}`,'Feasibility','affordance'],
    [String.raw`\lambda_{\mathrm{avail}}\mathcal{L}_{\mathrm{avail}}`,'Availability','availability']
   ];
   for(const [term,label,key] of terms)tex=tex.replace(term,String.raw`\htmlClass{objective-term term-${key}}{\underbrace{${term}}_{\text{${label}}}}`);
  }
  katex.render(tex,el,{displayMode:el.classList.contains('equation'),throwOnError:true,
   strict:code=>code==='htmlExtension'?'ignore':'error',trust:context=>context.command==='\\htmlClass'});
  el.querySelectorAll('.objective-term').forEach(term=>{
   const keys=term.classList.contains('term-order')?['selection','order','kl']:term.classList.contains('term-flow')?['flow']:term.classList.contains('term-affordance')?['affordance']:[];
   term.dataset.lossKeys=keys.join(' ');
   term.tabIndex=0;term.setAttribute('role','button');
   if(keys.length)term.setAttribute('aria-controls',keys.map(key=>'loss-'+key).join(' '));
   term.setAttribute('aria-label',term.classList.contains('term-order')?'Explain selection, ranking and regularization losses':term.classList.contains('term-flow')?'Explain generation loss':term.classList.contains('term-affordance')?'Explain feasibility loss':'Explain the availability penalty and its zero weight');
   term.title=term.getAttribute('aria-label');
  });
  if(el.dataset.objectiveAnnotations){
   // Fit the actual typeset width, including labels, without scaling hit targets.
   let pending=false, previousWidth=0;
   const fit=()=>{
    pending=false;
    const available=el.getBoundingClientRect().width;
    if(available<=2)return;
    el.style.setProperty('--objective-font-size','16px');
    let size=16;
    for(let pass=0;pass<3;pass++){
     const width=el.querySelector('.katex-display').getBoundingClientRect().width;
     if(width<=available-2)break;
     size=Math.floor(size*(available-2)/width*100)/100;
     el.style.setProperty('--objective-font-size',`${size}px`);
    }
   };
   const schedule=()=>{if(!pending){pending=true;requestAnimationFrame(fit);}};
   new ResizeObserver(entries=>{
    const width=entries[0].contentRect.width;
    if(width!==previousWidth){previousWidth=width;schedule();}
   }).observe(el);
   document.fonts.ready.then(schedule);
   document.fonts.addEventListener('loadingdone',schedule);
   schedule();
  }
 });
})();
