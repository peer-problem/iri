import * as THREE from 'three';

// Convert only the illustrator's filled silhouette to a distance field once.
// The SVG's separate outline layer is deliberately excluded.
export async function loadGiraffeDistance() {
  const response = await fetch('/shapes/giraffe.svg');
  if (!response.ok) throw new Error('기린 에셋을 불러오지 못했습니다.');
  const doc = new DOMParser().parseFromString(await response.text(), 'image/svg+xml');
  doc.querySelector('#line')?.remove();
  const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(doc)], {type:'image/svg+xml'}));
  const image = new Image();
  try {
    await new Promise<void>((resolve,reject)=>{image.onload=()=>resolve();image.onerror=()=>reject(new Error('기린 SVG를 읽지 못했습니다.'));image.src=url;});
    const size=256, canvas=document.createElement('canvas');canvas.width=canvas.height=size;
    const ctx=canvas.getContext('2d')!;ctx.drawImage(image,0,0,size,size);
    const pixels=ctx.getImageData(0,0,size,size).data;
    const inside=new Uint8Array(size*size);
    for(let i=0;i<inside.length;i++)inside[i]=pixels[i*4+3]>127?1:0;
    const distance=new Float32Array(size*size);distance.fill(1000);
    for(let y=1;y<size-1;y++)for(let x=1;x<size-1;x++){
      const i=y*size+x;
      if(inside[i]!==inside[i-1]||inside[i]!==inside[i+1]||inside[i]!==inside[i-size]||inside[i]!==inside[i+size])distance[i]=.5;
    }
    for(let y=1;y<size;y++)for(let x=1;x<size-1;x++){
      const i=y*size+x;distance[i]=Math.min(distance[i],distance[i-1]+1,distance[i-size]+1,distance[i-size-1]+Math.SQRT2,distance[i-size+1]+Math.SQRT2);
    }
    for(let y=size-2;y>=0;y--)for(let x=size-2;x>0;x--){
      const i=y*size+x;distance[i]=Math.min(distance[i],distance[i+1]+1,distance[i+size]+1,distance[i+size+1]+Math.SQRT2,distance[i+size-1]+Math.SQRT2);
    }
    const data=new Uint16Array(size*size);
    for(let i=0;i<data.length;i++)data[i]=THREE.DataUtils.toHalfFloat(distance[i]/size*1.8*(inside[i]?-1:1));
    const texture=new THREE.DataTexture(data,size,size,THREE.RedFormat,THREE.HalfFloatType);
    texture.minFilter=texture.magFilter=THREE.LinearFilter;texture.needsUpdate=true;
    return texture;
  } finally { URL.revokeObjectURL(url); }
}
