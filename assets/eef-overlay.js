/* EEF traces are display overlays: keep their recorded positions legible over the object. */
window.CLEAR_EEF_OVERLAY=function(viewer){
 const nodes=viewer?.mutable?.current?.nodeRefFromName;if(!nodes)return;
 for(const [name,node] of Object.entries(nodes)){
  const ghost=name.startsWith('/reference-ghost/')&&name.endsWith('-outline');
  const reference=/^\/(?:object-overlay\/(?:reference|lane-[01])|native-overlay\/object-reference)$/.test(name);
  if(!ghost&&!reference&&!/^\/(?:eef-overlay\/(?:trace|anchors|current)|native-overlay\/(?:eef-0|anchors-0|current-0))(?:-outline)?$/.test(name))continue;
  const rim=name.endsWith('-outline'),line=reference||name.endsWith('/trace')||name.endsWith('/eef-0');
  node.traverse(child=>{
   if(!child.material)return;
   child.renderOrder=line?80:rim?81:82;
   for(const material of Array.isArray(child.material)?child.material:[child.material]){
    material.depthTest=false;material.depthWrite=false;material.transparent=true;
    material.opacity=ghost?.8:reference?.78:line?.88:rim?.95:1;
   }
  });
 }
};
