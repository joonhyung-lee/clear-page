/* A single context summary precedes the two distinct sampling decisions. */
(() => {
 const layout=document.querySelector('.maze-order-layout');if(!layout)return;
 layout.querySelectorAll('.context-source,.context-target').forEach(e=>e.remove());
 const root=document.createElement('div');root.id='context-formation';root.className='context-formation';
 root.innerHTML='<div class="context-summary"><span>Scene + robot body</span><span aria-hidden="true">→</span><span>Planning context H</span><span aria-hidden="true">→</span><span>OrderNet</span></div>';
 layout.prepend(root);
})();
