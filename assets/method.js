/* Detailed equations remain available within optional disclosures. */
(() => {
 document.querySelectorAll('[data-tex]').forEach(el => {
  katex.render(el.dataset.tex,el,{displayMode:el.classList.contains('equation'),throwOnError:true,strict:'error'});
 });
})();
