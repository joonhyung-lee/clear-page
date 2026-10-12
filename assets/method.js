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
   term.tabIndex=0;term.setAttribute('role','button');
   term.setAttribute('aria-label',term.classList.contains('term-order')?'Highlight selection, ranking and regularization losses':term.classList.contains('term-flow')?'Highlight flow loss':term.classList.contains('term-affordance')?'Highlight affordance loss':'Availability has zero weight in this recorded run. Highlight the full objective loss.');
   term.title=term.getAttribute('aria-label');
  });
 });
})();
