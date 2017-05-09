# Gradient Painter

Info:

The Painter is aimed towards an easy way to setup gradients on objects that can be accessed and changed in the 3d view. The gradient direction can be determined from view and updated on the fly. Support for painting on multiple objects makes it easy to quickly create and iterate on a desired composition(e.g. color harmony in a level). The painter supports baking(Diffuse, AO) with quickly adjustable resolutions.

Doc:

V0.1
-Gradient painting on single object
-uses projected uv for baking
-Diffuse baking

V0.2
-Gradient painting on multiple objects
-View oriented gradient generation
-bakes to either generated, existing or projected uv map
-AO baking
-Change bake resolution and update existing maps(Avoid clutter)
