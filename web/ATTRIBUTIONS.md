# Visual implementation attributions

`public/previews/chat.webp` is a screenshot of this project's actual `/chat` interface, captured locally without a conversation or personal data. It is used only as a linked demo preview, not as a generated illustration.

Service links use the [Hugging Face brand SVG](https://huggingface.co/front/assets/huggingface_logo-noborder.svg) and the [GitHub mark from Primer Octicons](https://github.com/primer/octicons/blob/main/icons/mark-github-16.svg). They are stored locally under `public/brands/`. The Hugging Face asset has an added viewBox for proportional resizing; its artwork is unchanged. Octicons is MIT-licensed, with the notice in `licenses/OCTICONS-LICENSE.txt`. These marks identify the linked services and do not imply endorsement.

The landing page uses an original paper-style layout and five interactive Three.js technical illustrations authored in this repository. Procedural geometry, instanced weight matrices, physical materials, RoomEnvironment lighting and canvas-rendered text illustrate the product's input paths, QLoRA update mechanism, guarded routing, age settings and bounded conversation context. Generated bitmap illustrations are not included. WebGL failure falls back to semantic text. QLoRA's frozen-weight and trainable-adapter distinction follows the [original paper](https://arxiv.org/abs/2305.14314); displayed dimensions are illustrative rather than a literal model architecture. System serif fonts are used for the paper body. Paper Mono, Die Grotesk A and Die Grotesk B remain copied from the archived local Base UI 1.7.0 snapshot (`254f4744f0a241c20697b9eeab33402f4469a081`) under `reference/base-ui-site/fonts/`. The chat interface and landing wordmark use Die Grotesk. These assets are bundled locally. The landing styles are scoped and do not change `/chat`.

The Orb interface was copied and adapted into this repository from the private `peer-problem/iri-orb` prototype at commit `86df027488c582d293c0909b9ce80d3fa98705a9`. The production application is self-contained in `iri/web` and has no runtime or build dependency on that repository.

The shader hue rotation and simplex noise are adapted from [React Bits Orb](https://reactbits.dev/backgrounds/orb). Its MIT and Commons Clause terms are preserved in `licenses/REACT-BITS-LICENSE.md`.

The liquid separation scene adapts value noise, exponential smooth minimum, ray marching, and distance field normal techniques from [Interactive Droplets](https://github.com/koji014/interactive-droplets) and its [Codrops tutorial](https://tympanus.net/codrops/2025/06/09/how-to-create-interactive-droplet-like-metaballs-with-three-js-and-glsl/). The retrieved source had no standalone license. Provenance and the scope of adaptation are recorded in `licenses/INTERACTIVE-DROPLETS-NOTICE.md`.

The giraffe distance field was derived from an [OpenMoji](https://openmoji.org/) giraffe image and adapted into code. OpenMoji is licensed under CC BY-SA 4.0. The license text is preserved in `licenses/OPENMOJI-LICENSE.txt`.

Liquid glass controls use the published `@liquid-dom/react` package. Three-dimensional rendering uses Three.js. Their package license files are included by the package manager in installed dependencies and deployment license reporting.
