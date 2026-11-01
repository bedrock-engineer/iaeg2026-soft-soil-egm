// @types/three 0.140 has no typings for three's meshopt decoder; the part GLTFLoader uses
declare module "three/examples/jsm/libs/meshopt_decoder.module.js" {
  export const MeshoptDecoder: {
    supported: boolean;
    ready: Promise<void>;
    decodeGltfBuffer(...args: unknown[]): void;
  };
}
