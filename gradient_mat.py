import bpy
import gp_utils as gp
      
def add_node(context, mat, mask):
    """Returns a base node with the ramp for control"""
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    ramp = nodes.new("ShaderNodeValToRGB")
    mask = nodes.new("ShaderNodeTexImage")
    out = nodes['Diffuse BSDF']
    
    mask.image = mask
    
    links.new(mask.outputs[0], ramp.inputs[0])
    links.new(ramp.outputs[0], out.inputs[0])
    
    return ramp


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
            ob = context.active_object
            mat = gp.get_mat(context, ob)
            return {'FINISHED'}
        else:
            return {'CANCELLED'}

def register():
    bpy.util.register_class(GradientMat)

def unregister():
    bpy.utils.unregister_class(GradientMat)