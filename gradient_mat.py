import bpy
import mask_baking

def main(context):
    ob = context.active_object
    mat, output = mask_baking.create_mat(ob.name)

def add_node(context, mat, end_node, mask):
    """Returns a base node with I/O and the ramp for control"""
    nodes = mat.node_tree.nodes
    mix = nodes.new("ShaderNodeMixRGB")
    ramp = nodes.new("ShaderNodeValToRGB")
    mask = nodes.new("ShaderNodeTexImage")

    mix.blend_type = 'MULTIPLY'
    mix.inputs[0].default_value = 1
    mix.inputs[1].default_value = (1, 1, 1, 1)

    mask.image = mask

    return mix.inputs[1], mix.outputs[0], ramp


class GradientMat(bpy.types.Operator):
    """Creates the object's base material and related functions"""
    bl_idname = "GP.create_mat"
    bl_label = "Create Gradient Material"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        if self.poll(context):
            main(context)
            return {'FINISHED'}
        else:
            return {'CANCELLED'}

def register():
    bpy.util.register_class(GradientMat)

def unregister():
    bpy.utils.unregister_class(GradientMat)