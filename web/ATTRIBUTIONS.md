# Visual implementation attributions

The Orb interface was copied and adapted into this repository from the private `peer-problem/iri-orb` prototype at commit `86df027488c582d293c0909b9ce80d3fa98705a9`. The production application is self-contained in `iri/web` and has no runtime or build dependency on that repository.

The shader hue rotation and simplex noise are adapted from [React Bits Orb](https://reactbits.dev/backgrounds/orb). Its MIT and Commons Clause terms are preserved in `licenses/REACT-BITS-LICENSE.md`.

The liquid separation scene adapts value noise, exponential smooth minimum, ray marching, and distance field normal techniques from [Interactive Droplets](https://github.com/koji014/interactive-droplets) and its [Codrops tutorial](https://tympanus.net/codrops/2025/06/09/how-to-create-interactive-droplet-like-metaballs-with-three-js-and-glsl/). The retrieved source had no standalone license. Provenance and the scope of adaptation are recorded in `licenses/INTERACTIVE-DROPLETS-NOTICE.md`.

The giraffe distance field was derived from an [OpenMoji](https://openmoji.org/) giraffe image and adapted into code. OpenMoji is licensed under CC BY-SA 4.0. The license text is preserved in `licenses/OPENMOJI-LICENSE.txt`.

Liquid glass controls use the published `@liquid-dom/react` package. Three-dimensional rendering uses Three.js. Their package license files are included by the package manager in installed dependencies and deployment license reporting.
