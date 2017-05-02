bl_info = {
    "name" : "Gradient Painter",
    "author" : "Martin Durhuus",
    "version" : (0,1),
    "blender" : (2,78,0),
    "location" : "3d view",
    "description" : "A simple tool to quickly texture a mesh through a color ramp. Export currently gives you an .fbx and albedo map",
    "warning" : "Highly unstable and context sensitive",
    "category" : "Paint",
}

import bpy
from bpy.props import (
        StringProperty,
        BoolProperty,
        FloatProperty,
        IntProperty,
        EnumProperty,
        CollectionProperty,
        )

image_to_export = None
node_val_ramp = None
node_col_ramp = None

object_attr = {}
#Keep track of the main shader
mat = None

def init_settings(context):
    context.space_data.viewport_shade = 'MATERIAL'
    context.scene.render.engine = 'CYCLES'

def create_new_image(context, name, tex_type='COL'):
    tex_width = context.scene.texture_width
    tex_height = context.scene.texture_height
    if tex_type == 'AO':
        image = bpy.data.images.new(name=(name + "_ao"), width=tex_width, height=tex_height)
    elif tex_type == 'COL':
        image = bpy.data.images.new(name=(name + "_col"), width=tex_width, height=tex_height)
    return(image)

def texture_baking(context, mat, image, bake_type='DIFFUSE'):
    nodes = mat.node_tree.nodes
    scn = context.scene
    global object_attr
    image_node = nodes.new("ShaderNodeTexImage")
    image_node.image = image
    nodes.active = image_node
    scn.cycles.bake_type = bake_type
    if bake_type == 'AO':
        object_attr['AO_node'] = image_node
    elif bake_type == 'DIFFUSE':
        object_attr['DIF_node'] = image_node
        bake_settings = bpy.data.scenes[scn.name].render.bake
        bake_settings.use_pass_color = True
        bake_settings.use_pass_direct = False
        bake_settings.use_pass_indirect = False
    bpy.ops.object.bake(bake_type)

def create_base_material(context, mesh_name):
    mat = bpy.data.materials.new(mesh_name + "_mat")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    node_output = nodes.new("ShaderNodeOutputMaterial")
    return (mat, node_output)


def create_gradient_material(context, mesh_name):
    margin = 300 #Distance between nodes
    mat, node_output = create_base_material(context, mesh_name) #Empty mat with output
    nodes = mat.node_tree.nodes
    tmp_loc = node_output.location #Use tmp_loc as a location reference in node tree
    
    #
    #Node Creation(Right to left)
    #
    #Diffuse node
    node_diffuse = nodes.new("ShaderNodeBsdfDiffuse")
    node_diffuse.location.x = tmp_loc.x - margin
    tmp_loc = node_diffuse.location
    #Mix node set to Multiply(Specifically for AO)
    node_multiply_ao = nodes.new("ShaderNodeMixRGB")
    node_multiply_ao.blend_type = 'MULTIPLY'
    node_multiply_ao.inputs['Fac'].default_value = 1.0
    node_multiply_ao.location.x = tmp_loc.x - margin
    tmp_loc = node_multiply_ao.location
    #Mix node set to Multiply
    node_multiply = nodes.new("ShaderNodeMixRGB")
    node_multiply.blend_type = 'MULTIPLY'
    node_multiply.inputs['Fac'].default_value = 1.0
    node_multiply.location.x = tmp_loc.x - margin
    tmp_loc = node_multiply.location
    #First ramp: Used to colorize the mesh
    global node_col_ramp
    node_col_ramp = nodes.new("ShaderNodeValToRGB") #Make global for panel
    node_col_ramp.name = "Color"
    node_col_ramp.location.x = tmp_loc.x - margin
    tmp_loc = node_col_ramp.location
    #Second ramp: Used for value grading(Position map kinda)
    global node_val_ramp
    node_val_ramp = nodes.new("ShaderNodeValToRGB") #Make global for panel
    node_val_ramp.name = "Value"
    node_val_ramp.location.x = tmp_loc.x
    node_val_ramp.location.y = tmp_loc.y - margin
    #Gradient texture node
    node_gradient_tex = nodes.new("ShaderNodeTexGradient")
    node_gradient_tex.location.x = tmp_loc.x - margin
    tmp_loc = node_gradient_tex.location
    #Mapping node
    node_mapping = nodes.new("ShaderNodeMapping")
    node_mapping.location.x = (tmp_loc.x - margin) *1.1
    tmp_loc = node_mapping.location
    node_mapping.vector_type = 'TEXTURE'
    node_mapping.rotation[2] = 1.5708 #90d rotation in radians
    #UV Map node
    node_UV_map = nodes.new("ShaderNodeUVMap")
    node_UV_map.uv_map = "ProjectionMap"
    node_UV_map.location.x = tmp_loc.x - margin
    
    #Assign to object's attributes
    global object_attr
    object_attr['Material'] = mat
    object_attr['Col_ramp'] = node_col_ramp
    object_attr['Val_ramp'] = node_val_ramp
    object_attr['BSDF_node'] = node_diffuse
    object_attr['Mix_node'] = node_multiply_ao
    object_attr['Output_node'] = node_output

    #
    #Node linking(Left to right)
    #
    node_links = mat.node_tree.links
    node_links.new(node_UV_map.outputs[0], node_mapping.inputs[0])
    node_links.new(node_mapping.outputs[0], node_gradient_tex.inputs[0])
    node_links.new(node_gradient_tex.outputs[0], node_col_ramp.inputs[0])
    node_links.new(node_gradient_tex.outputs[0], node_val_ramp.inputs[0])
    node_links.new(node_col_ramp.outputs[0], node_multiply.inputs[1])
    node_links.new(node_val_ramp.outputs[0], node_multiply.inputs[2])
    node_links.new(node_multiply.outputs[0], node_multiply_ao.inputs[0])
    node_links.new(node_multiply_ao.outputs[0], node_diffuse.inputs[0])
    node_links.new(node_diffuse.outputs[0], node_output.inputs[0])

    return(mat)
    
def handle_projection(context):
    gen_uv = context.scene.generate_UV
    uv_textures = context.object.data.uv_textures
    if gen_uv:
        if len(uv_textures) == 0:    
            bpy.ops.uv.smart_project(angle_limit=66,
                                    island_margin=0.02,
                                    user_area_weight=0,
                                    use_aspect=False,
                                    stretch_to_bounds=True
                                    )
        elif uv_textures.active.name == "ProjectionMap" and \
        len(uv_textures) == 1:
            uv_map = bpy.ops.mesh.uv_texture_add()
            bpy.ops.uv.smart_project(angle_limit=66,
                                    island_margin=0.02,
                                    user_area_weight=0,
                                    use_aspect=False,
                                    stretch_to_bounds=True
                                    )
    for index, uv in enumerate(uv_textures):
        if uv.name == "ProjectionMap":
            projection_map = uv
            uv_textures.active_index = index
            bpy.ops.uv.project_from_view(orthographic=True,
                                         scale_to_bounds = True
                                         )
            return projection_map
    bpy.ops.mesh.uv_texture_add()
    projection_map = uv_textures[-1]
    projection_map.name = "ProjectionMap"
    bpy.ops.uv.project_from_view(orthographic=True,
                                 scale_to_bounds = True
                                 )
    return projection_map

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
        col.label(text="Gradient from View:")
        row = col.row(align=False)
        row.operator("bake.process_mesh")
        
        row = layout.row()
        layout.prop(scn, "generate_UV")

        layout.label("Baking:")
        row = layout.row()
        layout.prop(scn, "enable_ao")
        layout.prop(scn, "texture_width")
        layout.prop(scn, "texture_height")
        row.operator("bake.bake_texture")

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
        
class ProcessMesh(bpy.types.Operator):
    """Unwraps if required and applies gradient shader"""
    bl_idname = "bake.process_mesh"
    bl_label = "Calculate"
    bl_options = {'REGISTER', 'UNDO'}
    

    def execute(self, context):
        if context.active_object:
            init_settings(context)
            ob = context.active_object
            mesh_name = ob.name 
            if ob.mode != 'EDIT':
                bpy.ops.object.editmode_toggle()
            projection_map = handle_projection(context)
            if ob.active_material == None:
                ob.active_material = create_gradient_material(context, mesh_name)
            if ob.mode == 'EDIT':
                bpy.ops.object.editmode_toggle()
            return {'FINISHED'}
        else:
            self.report({'INFO'}, "Select an object to process")
            return {'FINISHED'}

class BakeTexture(bpy.types.Operator):
    """Creates texture and bakes an appropriate map"""
    bl_idname = "bake.bake_texture"
    bl_label = "Bake"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        enable_ao = context.scene.enable_ao

        if context.active_object:
            ob = context.active_object
            global mat
            if mat is None:
                self.report({'WARNING'}, "Calculate the gradient before baking!")
                return {'CANCELLED'}
            image_dif = create_new_image(context, ob.name)
            texture_baking(context, mat, image_dif)
            if enable_ao:
                image_ao = create_new_image(context, ob.name, tex_type='AO')
                texture_baking(context, mat, image_ao, bake_type='AO')
            return {'FINISHED'}
        else:
            self.report({'INFO'}, "Select a valid object for baking")

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

    bpy.types.Scene.enable_ao = BoolProperty(
        name="Enable AO: ",
        description="Enables Ambient Occlusion for baking",
        default=False,
    )
    bpy.utils.register_class(ProcessMesh)
    bpy.utils.register_class(MenuPanel)
    bpy.utils.register_class(BakeTexture)
    
def unregister():
    del bpy.types.Scene.generate_UV
    del bpy.types.Scene.texture_width
    del bpy.types.Scene.texture_height
    del bpy.types.Scene.enable_ao
    bpy.utils.unregister_class(ProcessMesh)
    bpy.utils.unregister_class(MenuPanel)
    bpy.utils.unregister_class(BakeTexture)
    
if __name__ == '__main__':
    register()
            