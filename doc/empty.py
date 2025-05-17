import sionna.rt
from sionna.rt import load_scene, Camera

scene = load_scene(sionna.rt.scene.etoile)
cam = Camera(position=[0, 0, 1000], look_at=[0, 1, 0])
scene.render(camera=cam)

import matplotlib.pyplot as plt

fig, ax = plt.subplots(1, 2, figsize=(9, 3.8))
ax[0].set(title="No interference", xlabel="I", ylabel="Q")
ax[0].grid(True)
ax[1].set(title="With jammer", xlabel="I", ylabel="Q")
ax[1].grid(True)
plt.tight_layout()
plt.show()
