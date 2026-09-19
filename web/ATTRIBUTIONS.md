# Visual implementation attributions

The landing page follows the local Peer Design `DESIGN.md` and `styles/tokens.css`. Link controls adapt `examples/base-ui/components/button/demos/hero/css-modules/index.module.css` from the archived Base UI 1.7.0 snapshot (`254f4744f0a241c20697b9eeab33402f4469a081`). Navigation remains native anchors rather than adopting button semantics. Die Grotesk A, Die Grotesk B and Paper Mono assets are copied from the same local reference's `reference/base-ui-site/fonts/`. These assets are bundled locally with no runtime dependency on the reference repository. The landing styles are scoped and do not change `/chat`.

The Orb interface was copied and adapted into this repository from the private `peer-problem/iri-orb` prototype at commit `86df027488c582d293c0909b9ce80d3fa98705a9`. The production application is self-contained in `iri/web` and has no runtime or build dependency on that repository.

The shader hue rotation and simplex noise are adapted from [React Bits Orb](https://reactbits.dev/backgrounds/orb). Its MIT and Commons Clause terms are preserved in `licenses/REACT-BITS-LICENSE.md`.

The liquid separation scene adapts value noise, exponential smooth minimum, ray marching, and distance field normal techniques from [Interactive Droplets](https://github.com/koji014/interactive-droplets) and its [Codrops tutorial](https://tympanus.net/codrops/2025/06/09/how-to-create-interactive-droplet-like-metaballs-with-three-js-and-glsl/). The retrieved source had no standalone license. Provenance and the scope of adaptation are recorded in `licenses/INTERACTIVE-DROPLETS-NOTICE.md`.

The giraffe distance field was derived from an [OpenMoji](https://openmoji.org/) giraffe image and adapted into code. OpenMoji is licensed under CC BY-SA 4.0. The license text is preserved in `licenses/OPENMOJI-LICENSE.txt`.

Liquid glass controls use the published `@liquid-dom/react` package. Three-dimensional rendering uses Three.js. Their package license files are included by the package manager in installed dependencies and deployment license reporting.
