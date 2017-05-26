import bpy
import gp_utils as gp

def enable_color_bake_settings():
    scn = bpy.context.scene
    bake_settings = bpy.data.scenes[scn.name].render.bake
    bake_settings.use_pass_color = True
    bake_settings.use_pass_direct = False
    bake_settings.use_pass_indirect = False

def create_bake_mat(context, name):
    """Returns a material and the output node of that material"""
    ob = context.active_object
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    out_node = mat.node_tree.nodes['Diffuse BSDF']
    out_node.name = 'out'

    return mat, out_node
    

def ao_mask(mask):
    """Returns an image with a baked Ambient Occlusion"""
    mask['mat'].node_tree.nodes.active = mask['image_node']
    bpy.ops.object.bake(type='AO')
    return mask['image']

def position_mask(context, mask):
    """Returns an image with a baked position mask"""
    ob = context.active_object
    scn = context.scene
    nodes = mask['mat'].node_tree.nodes
    #
    #Nodes Creation
    tex_coord = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.rotation[1] = 1.5708 #Radian rotation of 90 degrees in Y
    mapping.translation[0] = abs(gp.min_vertex(ob.data, 'z'))
    gr_tex = nodes.new("ShaderNodeTexGradient")
    #
    #Nodes linking
    links = mask['mat'].node_tree.links
    links.new(tex_coord.outputs[3], mapping.inputs[0])
    links.new(mapping.outputs[0], gr_tex.inputs[0])
    links.new(gr_tex.outputs[0], mask['output'].inputs[0])
    #
    #Baking
    mask['mat'].node_tree.nodes.active = mask['image_node']
    enable_color_bake_settings()
    bpy.ops.object.bake(type='DIFFUSE')
    return mask['image']

def curvature_mask(context, mask):
    """Returns an image with a baked curvature map. Map baked on a subdivided version."""
    bpy.ops.object.duplicate()
    ob = context.active_object
    bpy.ops.object.modifier_add(type='SUBSURF')
    subsurf = ob.modifiers[0]
    subsurf.subdivision_type = 'SIMPLE'
    
    ##Subdivides a mesh to a number around 5k+. This is due to curvature being calculated on vertices.
    while len(ob.data.vertices) < 5000:     #Number is currently an educated guess.
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.subdivide()
        bpy.ops.object.mode_set(mode='OBJECT')

    bpy.ops.object.mode_set(mode='OBJECT')

    nodes = mask['mat'].node_tree.nodes
    #Nodes Creation
    geo = nodes.new("ShaderNodeNewGeometry")
    #Nodes linking
    links = mask['mat'].node_tree.links
    links.new(geo.outputs[7], mask['output'].inputs[0])
    #Baking
    mask['mat'].node_tree.nodes.active = mask['image_node']
    enable_color_bake_settings()
    bpy.ops.object.bake(type='DIFFUSE')
    bpy.ops.object.delete()

    return mask['image']

def get_mask(context, width, height, map_type):
    """Returns an image with a baked map depending on the 'type' parameter"""
    mask = dict.fromkeys(['mat', 'output', 'image_node', 'image'])
    context.scene.render.engine = 'CYCLES'
    ob = context.active_object
    if ob.active_material:
        original_mat = ob.active_material #Might want to handle this!
        has_mat = True
    else:
        has_mat = False

    mask['mat'], mask['output'] = create_bake_mat(context, ''.join(['mask_', map_type])) #Output is actually a BSDF node
    ob.active_material = mask['mat']
    mask['image_node'] = mask['mat'].node_tree.nodes.new("ShaderNodeTexImage")
    mask['image'] = gp.get_img(ob, ''.join([ob.name, '_', map_type]), width, height)
    mask['image_node'].image = mask['image']

    if map_type == 'AO':
        img_mask = ao_mask(mask)
    elif map_type == 'POS':
        img_mask = position_mask(context, mask)
    elif map_type == 'CURVE':
        img_mask = curvature_mask(context, mask)
    if has_mat:
        ob.active_material = original_mat
    bpy.data.materials.remove(mask['mat'], do_unlink=True)
    return img_mask

class BakeMask(bpy.types.Operator):
    bl_idname = "bake.bake_maps"
    bl_label = "Pre-Process Mesh"
    bl_options = {'REGISTER', 'UNDO'}

    width = bpy.props.FloatProperty(
        name = "Width",
        default = 512,
    )
    height = bpy.props.FloatProperty(
        name = "Height",
        default = 512,
    )

    supported_maps = [
        ('AO', '', ''),
        ('POS', '', ''),
        ('CURVE', '', '')]

    bake_type = bpy.props.EnumProperty(
        name = "Bake Type",
        description = "Type of map needed baking for a mask",
        default = 'AO',
        items = supported_maps,
    )

    #classmethod is required when running a function from an instance of the class and in this case
    #the poll() method is called to check whether baking is possible.
    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        if self.poll(context):
            mask = get_mask(context, self.width, self.height, self.bake_type)
            mask.pack(as_png=True)
            return {'FINISHED'}
        else:
            return {'CANCELLED'}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "width")
        layout.prop(self, "height")
    
def register():
    bpy.utils.register_class(BakeMask)
    
def unregister():
    bpy.utils.unregister_class(BakeMask)

if __name__ == '__main__':
    register()