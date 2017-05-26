bl_info = {
    "name" : "Gradient Painter",
    "author" : "Martin Durhuus",
    "version" : (0,2),
    "blender" : (2,78,0),
    "location" : "3d view",
    "description" : "A simple tool to quickly texture a mesh through a color ramp. Export currently gives you an .fbx and albedo map",
    "warning" : "Highly unstable and context sensitive",
    "category" : "Paint",
}

#INFO:
#       GrP_ID: Unique ID given to selected/active object. Used to keep track of generated maps, materials for said object.
#       GrP_type: 'Special' Type of object. Distinquish e.g. multiple images for same object(Shared ID).
#       GrP types = ('UV', 'PROJ', 'COL', 'AO')

import bpy
from collections import OrderedDict
from bpy.props import (
        StringProperty,
        BoolProperty,
        FloatProperty,
        IntProperty,
        EnumProperty,
        CollectionProperty,
        )

node_val_ramp = None
node_col_ramp = None

####################################
####    UTILITIES
#

def min_vertex(mesh, axis):
    for i, vt in enumerate(mesh.vertices):
        v = eval('.'.join(['vt.co', axis]))
        if i == 0:
            min = v
        if v < min:
            min = v
    return min

def get_item(context, item, ob, map_type=None):
    """Returns item of interest if existing. Returns none if not"""
    if item == 'MAT':
        for mat in bpy.data.materials:
            try:
                if mat['ID'] == ob['ID']:
                    return mat
            except:
                continue
        return None
    elif item == 'IMG':
        for img in bpy.data.images:
            try:
                if img['ID'] == ob['ID'] and img['mask'] == map_type:
                    bpy.data.images.remove(img, do_unlink=True)
                    return None
            except:
                continue
        return None
    else:
        print("Wrong ID types!")

def get_mat(context, ob):
    """Returns/creates material that fits object ID"""
    mat = get_item(context, 'MAT', ob)
    if mat is None:
        mat = bpy.data.materials.new(ob.name)
        mat['ID'] = ob['ID']
    return mat

def get_img(ob, name, width, height, map_type):
    """Returns an image type"""
    img = get_item(bpy.context, 'IMG', ob, map_type)
    if img is None:
        img = bpy.data.images.new(name, width, height)
        img.use_fake_user = True
        img.pack(as_png=True)
        img['ID'] = ob['ID']
        img['mask'] = map_type
    return img

def check_id(context, ob):
    try:
        if ob['ID'] >= 0:
            return ob
    except:
        pass

    ob_IDs = []
    for ob in bpy.data.objects:
        try:
            if ob['ID'] >= 0:
                ob_IDs.append(ob['ID'])
        except:
            continue
    
    if len(ob_IDs) == 0:
        ob['ID'] = 0
    else:
        #Yes this is correct, don't do +=, it doesn't work.
        ob['ID'] = max(ob_IDs) + 1

####################################
####    MASK BAKING
#

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
    mapping.translation[0] = abs(min_vertex(ob.data, 'z'))
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
    mask['image'] = get_img(ob, ''.join([ob.name, '_', map_type]), width, height, map_type)
    mask['image_node'].image = mask['image']

    if map_type == 'AO':
        img_mask = ao_mask(mask)
        print("Should bake!")
    elif map_type == 'POS':
        img_mask = position_mask(context, mask)
    elif map_type == 'CURVE':
        img_mask = curvature_mask(context, mask)
    if has_mat:
        ob.active_material = original_mat
    bpy.data.materials.remove(mask['mat'], do_unlink=True)
    return img_mask

def smart_uv_project():
    bpy.ops.uv.smart_project(
        angle_limit=66,
        island_margin=0.02,
        user_area_weight=0,
        use_aspect=False,
        stretch_to_bounds=True
        )

def handle_projection(context):
    if len(context.object.data.uv_textures) == 0:
        uv_map = context.object.data.uv_textures.new()
        smart_uv_project()



####################################
####    Material Handling
#

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

####################################
####    CLASSES
#

class MenuPanel(bpy.types.Panel):
    bl_idname = "paint.gradient_texturing"
    bl_label = "Gradient Painter"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_category = "Arura"

    def draw(self, context):
        layout = self.layout
        scn = context.scene
        ob = context.active_object

        col = layout.column(align=False)
        col.label(text="Mask Baking:")
        row = col.row(align=False)
        layout.prop(scn, "texture_width")
        layout.prop(scn, "texture_height")
        row.operator("bake.bake_maps")

        if len(ob.material_slots.items()) > 0:
            ob_mat = ob.material_slots[0]
            try:
                layout.label("Texture Control:")
                row = layout.row()
                node_col_ramp = ob_mat.material.node_tree.nodes['Color']
                layout.template_color_ramp(node_col_ramp, "color_ramp", expand=True)
                node_val_ramp = ob_mat.material.node_tree.nodes['Value']
                layout.template_color_ramp(node_val_ramp, "color_ramp", expand=True)
            except:
                pass

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
        tex_width = context.scene.texture_width
        tex_height = context.scene.texture_height
        if self.poll(context):
            handle_projection(context)
            check_id(context, context.active_object)
            ##NEEDS CHANGING!: - Should use own draw method with class properties, and not scene properties.
            mask = get_mask(context, tex_width, tex_height, self.bake_type)
            mask.pack(as_png=True)

            return {'FINISHED'}
        else:
            return {'CANCELLED'}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "width")
        layout.prop(self, "height")

def register():
    #Scene properties
    bpy.types.Scene.generate_UV = BoolProperty(
        name="Generate UV",
        description="Generate new UV map for mesh "
        "(WARNING: Will remove existing UV map)",
        default=False,
    )

    bpy.types.Scene.texture_width = IntProperty(
        name="Width: ",
        description="Width of the texture bake",
        default=512,
    )

    bpy.types.Scene.texture_height = IntProperty(
        name="Height: ",
        description="Height of the texture bake",
        default=512,
    )
    bpy.utils.register_class(MenuPanel)
    bpy.utils.register_class(BakeMask)
    
def unregister():
    del bpy.types.Scene.texture_width
    del bpy.types.Scene.texture_height
    bpy.utils.unregister_class(MenuPanel)
    bpy.utils.unregister_class(BakeMask)
    
if __name__ == '__main__':
    register()
            