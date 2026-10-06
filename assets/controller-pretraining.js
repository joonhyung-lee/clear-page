/* One from-scratch training history per physical robot. */
(() => {
 const root=document.querySelector('#controller-pretraining');if(!root)return;
 let body='g1';
 root.dataset.body=body;
 function select(next){
  body=next;root.dataset.body=body;
  root.querySelectorAll('[data-loco-body]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.locoBody===body)));
  root.dispatchEvent(new CustomEvent('policy-body-change',{detail:{body}}));
 }
 root.querySelectorAll('[data-loco-body]').forEach(button=>button.onclick=()=>{if(body!==button.dataset.locoBody)select(button.dataset.locoBody);});
 const observer=new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting)){select(body);observer.disconnect();}},{rootMargin:'200px'});
 observer.observe(root);
 if(location.hash==='#spot-curriculum')select('spot');
})();
