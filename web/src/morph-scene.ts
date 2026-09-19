import * as THREE from 'three';
import { dropletFunctions } from './droplet-functions';
import { loadGiraffeDistance } from './giraffe-distance';

// Both the agent and the box exist in the same distance field at all times.
// The box starts inside the sphere and translates out; no mesh handoff occurs.
export function createMorphScene(scene: THREE.Scene, source: THREE.ShaderMaterial, camera: THREE.PerspectiveCamera) {
  const progress = { value: 0 };
  const shape = { value: 0 };
  const emptyTexture = new THREE.DataTexture(new Uint16Array([THREE.DataUtils.toHalfFloat(1)]), 1, 1, THREE.RedFormat, THREE.HalfFloatType);
  emptyTexture.needsUpdate = true;
  const giraffe = { value: emptyTexture };
  let alive = true;
  const ready = loadGiraffeDistance().then(texture => { if (!alive) {texture.dispose(); return;} giraffe.value=texture; });
  const cameraZ = { value: camera.position.z };
  const aspect = { value: camera.aspect };
  const center = { value: new THREE.Vector3(.12, 0, 0) };
  const blend = { value: 7 };
  const shapeRotation = { value: new THREE.Matrix3() };
  const rotationMatrix = new THREE.Matrix4();
  const rotationEuler = new THREE.Euler();
  const cursor = new THREE.Vector2();
  const cursorSmooth = new THREE.Vector2();
  let cursorPresent = false;
  const envelope = { value: 0 };
  const audioShiftA = { value: new THREE.Vector3() };
  const audioShiftB = { value: new THREE.Vector3() };
  const clipBounds = { value: new THREE.Vector4(-1, -1, 1, 1) };
  const shade = source.fragmentShader
    .replace('varying vec3 vNormal;', '')
    .replace('varying vec3 vPosition;', '')
    .replace('varying vec3 vView;', '')
    .replace('void main() {', 'vec4 shadeSurface(vec3 vPosition, vec3 vNormal, vec3 vView) {')
    .replace('gl_FragColor =', 'return');
  const fragmentShader = `
    ${shade}
    ${dropletFunctions}
    uniform float uProgress;
    uniform int uShape;
    uniform sampler2D uGiraffe;
    uniform float uCameraZ;
    uniform float uAspect;
    uniform float uLevel;
    uniform float uTalking;
    uniform vec3 uCenter;
    uniform mat3 uShapeRotation;
    uniform float uBlend;
    uniform float uEnvelope;
    uniform vec3 uAudioShiftA;
    uniform vec3 uAudioShiftB;
    varying vec2 vUv;
    mat2 rotate2(float a) { float s=sin(a),c=cos(a); return mat2(c,-s,s,c); }
    float roundedBox(vec3 p) {
      p.xz = rotate2(.48) * p.xz;
      p.yz = rotate2(-.23) * p.yz;
      vec3 q = abs(p) - vec3(.34);
      return length(max(q,0.0)) + min(max(q.x,max(q.y,q.z)),0.0) - .10;
    }
    float extrude(float d, float z, float depth) {
      vec2 w=vec2(d,abs(z)-depth);
      return min(max(w.x,w.y),0.0)+length(max(w,0.0));
    }
    float triangle(vec3 p) {
      p.xz=rotate2(.10)*p.xz;
      vec2 q=p.xy;
      const float k=1.7320508;
      q.x=abs(q.x)-.54; q.y=q.y+.54/k;
      if(q.x+k*q.y>0.0)q=vec2(q.x-k*q.y,-k*q.x-q.y)*.5;
      q.x-=clamp(q.x,-1.08,0.0);
      float d=-length(q)*sign(q.y);
      return extrude(d,p.z,.10)-.035;
    }
    float giraffeShape(vec3 p) {
      p.xz=rotate2(.10)*p.xz;
      vec2 uv=vec2(p.x/1.8+.5,.5-p.y/1.8);
      float d=texture2D(uGiraffe,clamp(uv,vec2(.002),vec2(.998))).r;
      d+=length(max(abs(p.xy)-vec2(.895),0.0));
      return extrude(d,p.z,.075)-.012;
    }
    float map(vec3 p) {
      float wave = 0.0;
      if (uLevel > .0001) { wave = snoise3(p*1.2+uAudioShiftA)*.9;
      wave += snoise3(p*2.0+uAudioShiftB)*.1;
      }
      float sphere = length(p) - (1.0+uLevel*.09+wave*uLevel*.30);
      vec3 localPoint = uShapeRotation * (p-uCenter);
      float box = uShape == 0 ? roundedBox(localPoint) : (uShape == 1 ? triangle(localPoint) : giraffeShape(localPoint));
      float distanceField = smoothMin(sphere,box,uBlend);
      // Localized multi-scale noise warps the shared neck without disturbing
      // the resting agent or making a second ball to swap for the box.
      if (uEnvelope < .001) return distanceField;
      float junction = exp(-dot(p-vec3(1.05,.17,0.0),p-vec3(1.05,.17,0.0))*3.0);
      if (junction < .002) return distanceField;
      float n = noise3D(p*4.2+vec3(uTime*.55,-uTime*.32,uTime*.2))-.5;
      n += .35*(noise3D(p*8.0-vec3(uTime*.4))-.5);
      return distanceField + n*.18*uEnvelope*junction;
    }
    vec3 normalAt(vec3 p) {
      const float e=.0015;
      return normalize(vec3(map(p+vec3(e,0,0))-map(p-vec3(e,0,0)),map(p+vec3(0,e,0))-map(p-vec3(0,e,0)),map(p+vec3(0,0,e))-map(p-vec3(0,0,e))));
    }
    void main() {
      vec2 screen=vUv*2.0-1.0;
      vec3 origin=vec3(0,0,uCameraZ);
      vec3 direction=normalize(vec3(screen.x*uAspect*.286745,screen.y*.286745,-1.0));
      // Conservative bounds include maximum audio deformation, smooth-union
      // expansion and junction noise. Empty rays never evaluate the field.
      vec3 boundsMin=vec3(-1.65,-1.65,-1.65);
      vec3 boundsMax=vec3(max(1.65,uCenter.x+1.20),1.65,1.65);
      vec3 inverseRay=1.0/(direction+vec3(1e-8));
      vec3 a=(boundsMin-origin)*inverseRay;
      vec3 b=(boundsMax-origin)*inverseRay;
      vec3 entry=min(a,b), exitPoint=max(a,b);
      float nearDistance=max(max(entry.x,entry.y),entry.z);
      float farDistance=min(min(exitPoint.x,exitPoint.y),exitPoint.z);
      if(farDistance<max(nearDistance,0.0)) discard;
      float travel=max(0.0,nearDistance);
      bool hit=false;
      vec3 p=origin;
      for(int i=0;i<100;i++) {
        p=origin+direction*travel;
        float d=map(p);
        if(d<.0012){hit=true;break;}
        travel+=max(d*.65,.0006);
        if(travel>farDistance)break;
      }
      if(!hit) discard;
      vec3 n=normalAt(p);
      gl_FragColor=shadeSurface(p,n,-direction);
    }
  `;
  const material = new THREE.ShaderMaterial({
    uniforms: {...source.uniforms, uProgress: progress, uShape: shape, uGiraffe: giraffe, uCameraZ: cameraZ, uAspect: aspect, uCenter: center, uShapeRotation: shapeRotation, uBlend: blend, uEnvelope: envelope, uAudioShiftA: audioShiftA, uAudioShiftB: audioShiftB, uClipBounds: clipBounds},
    vertexShader: 'uniform vec4 uClipBounds; varying vec2 vUv; void main(){vec2 clip=mix(uClipBounds.xy,uClipBounds.zw,uv);vUv=clip*.5+.5;gl_Position=vec4(clip,0.0,1.0);}',
    fragmentShader, transparent:true, depthWrite:false, depthTest:false,
  });
  const geometry=new THREE.PlaneGeometry(2,2);
  const mesh=new THREE.Mesh(geometry,material);mesh.frustumCulled=false;scene.add(mesh);
  let target=0, queued=-1;
  return {
    ready,
    pointer(x:number,y:number) { cursor.set(x,y); cursorPresent=true; },
    leave() { cursorPresent=false; },
    select(index:number) {
      queued=index;
      if(progress.value <= .0001) {if(index>=0)shape.value=index;target=index<0?0:1;queued=-1;}
      else target=0;
    },
    update(dt:number,_time:number,reduced:boolean) {
      const delta=target-progress.value;
      progress.value=reduced?target:progress.value+Math.sign(delta)*Math.min(Math.abs(delta),dt/(target === 1 ? 1.2 : .7));
      if(progress.value===0 && queued>=0){shape.value=queued;queued=-1;target=1;}
      cameraZ.value=camera.position.z;aspect.value=camera.aspect;
      const settled=THREE.MathUtils.smoothstep(progress.value,.75,1);
      const deltaCursorX=cursorPresent ? THREE.MathUtils.clamp((cursor.x-1.92)*.10,-.12,.12) : 0;
      const deltaCursorY=cursorPresent ? THREE.MathUtils.clamp((cursor.y-.35)*.10,-.10,.10) : 0;
      const follow=1-Math.exp(-Math.min(dt,.05)*5);
      cursorSmooth.x+=(deltaCursorX-cursorSmooth.x)*follow;
      cursorSmooth.y+=(deltaCursorY-cursorSmooth.y)*follow;
      const bob=reduced ? 0 : Math.sin(_time*.85)*.035;
      center.value.set(.12+progress.value*1.80,progress.value*.35+bob*settled,0);
      const pitch=reduced ? 0 : (Math.sin(_time*.61)*.035-cursorSmooth.y)*settled;
      const yaw=reduced ? 0 : (Math.sin(_time*.47)*.065+cursorSmooth.x)*settled;
      const roll=reduced ? 0 : Math.sin(_time*.56)*.025*settled;
      rotationEuler.set(pitch,yaw,roll);
      rotationMatrix.makeRotationFromEuler(rotationEuler);
      shapeRotation.value.setFromMatrix4(rotationMatrix).transpose();
      const blendT=THREE.MathUtils.clamp((progress.value-.68)/.32,0,1);
      blend.value=7+11*blendT*blendT*(3-2*blendT);
      envelope.value=Math.sin(progress.value*Math.PI);
      const clock=source.uniforms.uTime.value*(.65+.40*source.uniforms.uTalking.value);
      audioShiftA.value.set(clock*.43,-clock*.30,clock*.27);
      audioShiftB.value.set(-clock*.25,clock*.35,0);
      // Rasterize only the projected bounds, preserving the original pixel grid.
      const yScale=1/((camera.position.z-1.65)*.286745);
      const xScale=yScale/camera.aspect;
      clipBounds.value.set(Math.max(-1,-1.65*xScale),Math.max(-1,-1.65*yScale),Math.min(1,Math.max(1.65,center.value.x+1.20)*xScale),Math.min(1,1.65*yScale));
      return `${shape.value}:${progress.value.toFixed(3)}:${target}:${queued}`;
    },
    dispose(){alive=false;scene.remove(mesh);geometry.dispose();material.dispose();giraffe.value.dispose();if(giraffe.value!==emptyTexture)emptyTexture.dispose();},
  };
}
