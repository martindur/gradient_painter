import bpy
from bpy.props import (
        StringProperty,
        BoolProperty,
        FloatProperty,
        IntProperty,
        EnumProperty,
        CollectionProperty,
        )

DRAWLIST = []

def min_vertex(mesh, axis):
    """Finds the minimum positioned vertex in mesh given axis"""
    for i, vt in enumerate(mesh.vertices):
        v = eval('.'.join(['vt.co', axis]))
        if i == 0:
            min = v
        if v < min:
            min = v
    return min

def enable_color_bake_settings():
    scn = bpy.context.scene
    bake_settings = bpy.data.scenes[scn.name].render.bake
    bake_settings.use_pass_color = True
    bake_settings.use_pass_direct = False
    bake_settings.use_pass_indirect = False

def smart_uv_project():
    """Pre-defined settings for existing uv projection OT"""
    bpy.ops.uv.smart_project(
        angle_limit=66,
        island_margin=0.02,
        user_area_weight=0,
        use_aspect=False,
        stretch_to_bounds=True
        )

def handle_projection(context):
    """Creates a UV map if none exists"""
    if len(context.object.data.uv_textures) == 0:
        uv_map = context.object.data.uv_textures.new()
        smart_uv_project()

def get_img(ob, name, width, height):
    """Returns an image type"""
    img = bpy.data.images.new(name, width, height)
    img.use_fake_user = True
    return img

def check_img(ob, map_type):
    """Checks if an Image node is selected with an active image. Returns image if true"""
    try:
        nodes = ob.active_material.node_tree.nodes
        for node in nodes:
            if node.label == map_type:
                return node.image
    except:
        pass
    try:
        nodes = ob.active_material.node_tree.nodes
        nodes.active.label = map_type
        return nodes.active.image
    except:
        return None

def create_bake_mat(context, name):
    """Returns a material and the output node of that material"""
    ob = context.active_object
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    out_node = mat.node_tree.nodes['Diffuse BSDF']
    out_node.name = 'out'

    return mat, out_node

def ao_map(map):
    """Returns an image with a baked Ambient Occlusion"""
    map['mat'].node_tree.nodes.active = map['image_node']
    bpy.ops.object.bake(type='AO')
    return map['image']

def position_map(context, map):
    """Returns an image with a baked position map"""
    ob = context.active_object
    scn = context.scene
    nodes = map['mat'].node_tree.nodes
    #
    #Nodes Creation
    tex_coord = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.rotation[1] = 1.5708 #Radian rotation of 90 degrees in Y
    mapping.translation[0] = abs(min_vertex(ob.data, 'z'))
    gr_tex = nodes.new("ShaderNodeTexGradient")
    #
    #Nodes linking
    links = map['mat'].node_tree.links
    links.new(tex_coord.outputs[3], mapping.inputs[0])
    links.new(mapping.outputs[0], gr_tex.inputs[0])
    links.new(gr_tex.outputs[0], map['output'].inputs[0])
    #
    #Baking
    map['mat'].node_tree.nodes.active = map['image_node']
    enable_color_bake_settings()
    bpy.ops.object.bake(type='DIFFUSE')
    return map['image']

def curvature_map(context, map):
    """Returns an image with a baked curvature map. Map baked on a subdivided version."""
    original_ob = context.active_object
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

    nodes = map['mat'].node_tree.nodes
    #Nodes Creation
    geo = nodes.new("ShaderNodeNewGeometry")
    #Nodes linking
    links = map['mat'].node_tree.links
    links.new(geo.outputs[7], map['output'].inputs[0])
    #Baking
    map['mat'].node_tree.nodes.active = map['image_node']
    enable_color_bake_settings()
    bpy.ops.object.bake(type='DIFFUSE')
    bpy.ops.object.delete()
    original_ob.select = True
    return map['image']

def get_map(context, width, height, map_type):
    """Returns an image with a baked map depending on the 'type' parameter"""
    map = dict.fromkeys(['mat', 'output', 'image_node', 'image'])
    context.scene.render.engine = 'CYCLES'
    ob = context.active_object
    if ob.active_material:
        original_mat = ob.active_material #Might want to handle this!
        has_mat = True
    else:
        has_mat = False
    
    #Check for existing image that the user has selected.
    map['image'] = check_img(ob, map_type)

    map['mat'], map['output'] = create_bake_mat(context, ''.join(['map_', map_type])) #Output is actually a BSDF node
    ob.active_material = map['mat']
    map['image_node'] = map['mat'].node_tree.nodes.new("ShaderNodeTexImage")
    if map['image'] is None:
        map['image'] = get_img(ob, ''.join([ob.name, '_', map_type]), width, height)
    map['image_node'].image = map['image']

    if map_type == 'AO':
        img_map = ao_map(map)
    elif map_type == 'POS':
        img_map = position_map(context, map)
    elif map_type == 'CURVE':
        img_map = curvature_map(context, map)
    if has_mat:
        ob.active_material = original_mat
    bpy.data.materials.remove(map['mat'], do_unlink=True)
    return img_map

class BakeMap(bpy.types.Operator):
    bl_idname = "bake.bake_maps"
    bl_label = "Bake"
    bl_options = {'REGISTER', 'UNDO'}

    #classmethod is required when running a function from an instance of the class and in this case
    #the poll() method is called to check whether baking is possible.
    @classmethod
    def poll(cls, context):
        rd = context.scene.render.engine
        return context.active_object is not None and rd == 'CYCLES'

    def execute(self, context):
        tex_width = context.scene.texture_width
        tex_height = context.scene.texture_height
        bake_type = context.scene.bake_type
        if self.poll(context):
            ob = context.active_object
            handle_projection(context)
            ##NEEDS CHANGING!: - Should use own draw method with class properties, and not scene properties.
            map = get_map(context, tex_width, tex_height, bake_type)
            map.pack(as_png=True)
            #mat = get_mat(context, ob, map, self.bake_type)
            #ob.active_material = mat
            return {'FINISHED'}
        else:
            return {'CANCELLED'}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "width")
        layout.prop(self, "height")

class BakeMenu(bpy.types.Panel):
    #bl_idname = "bake.bake_menu"
    bl_label = "Baking"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_category = "Arura"
    COMPAT_ENGINES = {'CYCLES'}

    def draw(self, context):
        layout = self.layout
        scn = context.scene
        cbk = scn.render.bake

        row = layout.row(align=True)
        #row.alignment = 'EXPAND'
        row.prop(scn, "texture_width")
        row.prop(scn, "texture_height")
        
        row = layout.row()
        row.prop(scn, "bake_type")

        row = layout.row()
        row.prop(cbk, "margin")

        row = layout.row()
        row.operator("bake.bake_maps", icon='RENDER_STILL')

class WidgetUI(bpy.types.Panel):
    bl_idname = "paint.widget_ui"
    bl_label = "GameTex Tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_category = "Arura"
    
    def draw_node(self, node):
        layout = self.layout
        if node.type == 'VALTORGB':
            return layout.template_color_ramp(node, "color_ramp", expand=True)


    def draw(self, context):
        layout = self.layout
        scn = context.scene
        
        col = layout.column(align=False)
        col.label(text="Parameters:")
        
        if context.active_object:
            ob = context.active_object
            if ob.active_material:
                mat = ob.active_material
                if mat.use_nodes:
                    nodes = mat.node_tree.nodes
                    global DRAWLIST
                    row = layout.row()
                    for node in nodes:
                        if node.use_custom_color:
                            if node in DRAWLIST:
                                continue
                            else:
                                DRAWLIST.append(node)
                        elif not node.use_custom_color and node in DRAWLIST:
                            DRAWLIST.remove(node)
                    for node in DRAWLIST:
                        row = layout.row()
                        row.label(node.label)
                        self.draw_node(node)
        
classes = [
    BakeMenu,
    WidgetUI,
    BakeMap   
]

def register():
    ##Scene properties
    bpy.types.Scene.texture_width = IntProperty(
        name="W: ",
        description="Width of the texture bake",
        default=512,
    )

    bpy.types.Scene.texture_height = IntProperty(
        name="H: ",
        description="Height of the texture bake",
        default=512,
    )
    bpy.types.Scene.bake_type = EnumProperty(
        name = "Map ",
        description = "Type of map needed baking for a map",
        default = 'AO',
        items = [('AO', 'Ambient Occlusion', ''),
                 ('CURVE', 'Curvature', ''),
                 ('POS', 'Position', '')]
    )

    for c in classes:
        bpy.utils.register_class(c)
    
def unregister():
    del bpy.types.Scene.texture_width
    del bpy.types.Scene.texture_height
    del bpy.types.Scene.bake_type

    for c in classes:
        bpy.utils.unregister_class(c)
    
if __name__ == '__main__':
    register()