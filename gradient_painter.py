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

def init_settings(context, obj):
    #Basic settings required to view the gradient.
    context.space_data.viewport_shade = 'MATERIAL'
    context.scene.render.engine = 'CYCLES'
    try:
        if obj['GrP_ID'] >= 0:
            return obj
    except:
        pass

    #Set object ID
    object_IDs = []
    for ob in bpy.data.objects:
        try:
            if ob['GrP_ID'] >= 0:
                object_IDs.append(ob['GrP_ID'])
        except:
            continue

    if len(object_IDs) == 0:
        obj['GrP_ID'] = 0
    else:
        obj['GrP_ID'] = max(object_IDs) + 1
    return obj

def create_new_image(context, name, tex_type='COL'):
    ob = context.active_object
    tex_width = context.scene.texture_width
    tex_height = context.scene.texture_height

    for image in bpy.data.images:
        try:
            if image['GrP_ID'] == ob['GrP_ID'] and image['GrP_type'] == tex_type:
                bpy.data.images.remove(image, do_unlink=True)
        except:
            continue

    if tex_type == 'AO':
        image = bpy.data.images.new(name=(name + "_ao"), width=tex_width, height=tex_height)
        image['GrP_type'] = 'AO'
    elif tex_type == 'COL':
        image = bpy.data.images.new(name=(name + "_col"), width=tex_width, height=tex_height)
        image['GrP_type'] = 'COL'

    #Check for existing image for this object of same requested type.
    for img in bpy.data.images:
        try:
            if img['GrP_ID'] == ob['GrP_ID'] and img['GrP_type'] == tex_type:
                img['GrP_ID'] = -1
        except:
            continue

    image['GrP_ID'] = ob['GrP_ID']

    return(image)

def texture_baking(context, mat, image, bake_type='DIFFUSE'):
    tex_width = context.scene.texture_width
    tex_height = context.scene.texture_height
    nodes = mat.node_tree.nodes
    scn = context.scene
    if nodes.get('Image Texture'):
        image_node = nodes.get('Image Texture')
    else:
        image_node = nodes.new("ShaderNodeTexImage")
    image_node.image = image
    nodes.active = image_node
    scn.cycles.bake_type = bake_type
    #render = bpy.data.scenes[scn.name].render
    #render.bake_type = bake_type
    if bake_type == 'DIFFUSE':
        #Only include color, no indirect/direct lighting info
        bake_settings = bpy.data.scenes[scn.name].render.bake
        bake_settings.use_pass_color = True
        bake_settings.use_pass_direct = False
        bake_settings.use_pass_indirect = False
    bpy.ops.object.bake(type=bake_type, width = tex_width, height = tex_height)
    return {'FINISHED'}

def create_base_material(context, mesh_name):
    mat = bpy.data.materials.new(mesh_name + "_mat")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    node_output = nodes.new("ShaderNodeOutputMaterial")
    return (mat, node_output)


def create_gradient_material(context, mesh_name):
    ob = context.active_object
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
    node_multiply_ao.inputs[2].default_value = (1, 1, 1, 1)
    node_multiply_ao.location.x = tmp_loc.x - margin
    tmp_loc = node_multiply_ao.location
    #Mix node set to Multiply
    node_multiply = nodes.new("ShaderNodeMixRGB")
    node_multiply.blend_type = 'MULTIPLY'
    node_multiply.inputs['Fac'].default_value = 1.0
    node_multiply.location.x = tmp_loc.x - margin
    tmp_loc = node_multiply.location
    #First ramp: Used to colorize the mesh
    #global node_col_ramp
    node_col_ramp = nodes.new("ShaderNodeValToRGB") #Make global for panel
    node_col_ramp.name = "Color"
    node_col_ramp.location.x = tmp_loc.x - margin
    tmp_loc = node_col_ramp.location
    #Second ramp: Used for value grading(Position map kinda)
    #global node_val_ramp
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

    #Assign ID to relevant objects
    mat['GrP_ID'] = ob['GrP_ID']
    node_col_ramp['GrP_ID'] = ob['GrP_ID']
    node_val_ramp['GrP_ID'] = ob['GrP_ID']
    node_diffuse['GrP_ID'] = ob['GrP_ID']
    node_multiply_ao['GrP_ID'] = ob['GrP_ID']
    node_output['GrP_ID'] = ob['GrP_ID']

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
    node_links.new(node_multiply.outputs[0], node_multiply_ao.inputs[1])
    node_links.new(node_multiply_ao.outputs[0], node_diffuse.inputs[0])
    node_links.new(node_diffuse.outputs[0], node_output.inputs[0])

    return(mat)
    
def smart_uv_project():
    bpy.ops.uv.smart_project(angle_limit=66,
                             island_margin=0.02,
                             user_area_weight=0,
                             use_aspect=False,
                             stretch_to_bounds=True
                             )





def handle_projection(context):
    ob = context.active_object
    use_proj = context.scene.use_projection
    uv_textures = context.object.data.uv_textures

    #
    #Take care of all(as if) cases for uv maps, and adds a projection map accordingly.
    #
    if len(uv_textures) == 0:
        uv_map = uv_textures.new() #Default settings creates uv map with name 'UVMap'
        smart_uv_project() #Unwraps the current uv map
        proj_map = uv_textures.new("ProjectionMap")

    elif len(uv_textures) == 1:
        if uv_textures[0].name == "ProjectionMap":
            proj_map = uv_textures[0]
            uv_map = uv_textures.new()
            smart_uv_project()
        else:
            uv_map = uv_textures[0]
            uv_map.name = "UVMap"
            proj_map = uv_textures.new("ProjectionMap")
    
    else:
        for uv in uv_textures:
            if not any(uv.name == "ProjectionMap" for uv in uv_textures):
                proj_map = uv_textures.new("ProjectionMap")
            else:
                if uv.name == "ProjectionMap":
                    proj_map = uv
        for uv in uv_textures:
            if uv.name != "ProjectionMap":
                uv_map = uv
                uv_map.name = "UVMap"
                break

    ##Default behaviour for projecting, needed for the gradient material to work.
    uv_textures.active = proj_map
    bpy.ops.uv.project_from_view(orthographic=True, scale_to_bounds = True)
    if not use_proj:
        uv_textures.active = uv_map

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
        layout.prop(scn, "use_projection")
        row = col.row(align=False)
        try:
            if ob['GrP_ID'] >= 0:
                gr_label = "Update"
        except:
            gr_label = "Calculate"
        row.operator("bake.process_mesh", text=gr_label)

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

    def check_materials(self, context, obj, mesh_name):
        """Checks existing materials. If a material is missing, 
        this function calls the create function for materials."""
        try:
            if obj.active_material['GrP_ID'] >= 0:
                return
        except:
            if len(bpy.data.materials) == 0:
                obj.active_material = create_gradient_material(context, mesh_name)
            mat_id_exists = False
            for mat in bpy.data.materials:
                try:
                    if mat['GrP_ID'] == obj['GrP_ID']:
                        obj.active_material = mat
                        mat_id_exists = True
                        break
                except:
                    continue
            if mat_id_exists is False:
                obj.active_material = create_gradient_material(context, mesh_name)

    def execute(self, context):
        if context.active_object:
            ob = context.active_object
            mesh_name = ob.name
            ob = init_settings(context, ob)
            if ob.mode != 'EDIT':
                bpy.ops.object.editmode_toggle()
            handle_projection(context)
            self.check_materials(context, ob, mesh_name)
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

    def check_images(self, context, ob, tex_type='COL'):
        for image in bpy.data.images:
            try:
                if image['GrP_ID'] == ob['GrP_ID'] and image['GrP_type'] == tex_type:
                    if image.size[0] == context.scene.texture_width and image.size[1] == context.scene.texture_height:
                        return image
            except:
                continue
        return create_new_image(context, ob.name, tex_type)

    def execute(self, context):
        enable_ao = context.scene.enable_ao
        if context.active_object:
            ob = context.active_object
            
            #Find mat with the proper object ID
            try:
                if ob.active_material['GrP_ID'] >= 0:
                    mat = ob.active_material
            except:
                for mt in bpy.data.materials:
                    try:
                        if mt['GrP_ID'] == ob['GrP_ID']:
                            mat = mt
                    except:
                        continue

            if mat is None:
                self.report({'WARNING'}, "Calculate the gradient before baking!")
                return {'CANCELLED'}
            self.check_images
            image_dif = self.check_images(context, ob)
            texture_baking(context, mat, image_dif)
            if enable_ao:
                image_ao = self.check_images(context, ob, tex_type='AO')
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
        name="Enable AO",
        description="Enables Ambient Occlusion for baking",
        default=False,
    )
    bpy.types.Scene.use_projection = BoolProperty(
        name="Use Projection Map",
        description="Bake to the projection UV map(Useful for texture size with simple linear gradients)",
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
            