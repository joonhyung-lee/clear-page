/* Paper equations, with descriptive underbraces on the combined objective. */
(() => {
 document.querySelectorAll('[data-tex]').forEach(el => {
  let tex=el.dataset.tex;
  if(el.dataset.objectiveAnnotations){
   const terms=[
    [String.raw`\mathcal{L}_{\mathrm{order}}`,'Selection and ranking','order'],
    [String.raw`\lambda_{\mathrm{flow}}\mathcal{L}_{\mathrm{flow}}`,'Object generation','flow'],
    [String.raw`\lambda_{\mathrm{aff}}\mathcal{L}_{\mathrm{aff}}`,'Interaction feasibility','affordance'],
    [String.raw`\lambda_{\mathrm{avail}}\mathcal{L}_{\mathrm{avail}}`,'First interaction','availability']
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
