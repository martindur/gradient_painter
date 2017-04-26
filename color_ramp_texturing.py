import bpy
from bpy.props import *

bl_info = {
    "name" : "Gradient Texturing",
    "author" : "Martin Durhuus",
    "version" : (0,1),
    "blender" : (2,78,0),
    "location" : "3d view",
    "description" : "A simple tool to quickly texture a mesh through a color ramp. Export currently gives you an .fbx and albedo map",
    "warning" : "Highly unstable and context sensitive",
    "category" : "Paint",
}

image_to_export = None
node_val_ramp = None
node_col_ramp = None

def create_new_image(context, name):
    image = bpy.data.images.new(name=(name + "_col"), width=1, height=256)
    return(image)


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
    #Texture coord node
    node_tex_coord = nodes.new("ShaderNodeTexCoord")
    node_tex_coord.location.x = tmp_loc.x - margin
    
    #
    #Node linking(Left to right)
    #
    node_links = mat.node_tree.links
    node_links.new(node_tex_coord.outputs[2], node_mapping.inputs[0])
    node_links.new(node_mapping.outputs[0], node_gradient_tex.inputs[0])
    node_links.new(node_gradient_tex.outputs[0], node_col_ramp.inputs[0])
    node_links.new(node_gradient_tex.outputs[0], node_val_ramp.inputs[0])
    node_links.new(node_col_ramp.outputs[0], node_multiply.inputs[1])
    node_links.new(node_val_ramp.outputs[0], node_multiply.inputs[2])
    node_links.new(node_multiply.outputs[0], node_diffuse.inputs[0])
    node_links.new(node_diffuse.outputs[0], node_output.inputs[0])
    
    #
    #Create texture image for baking
    #
    image = create_new_image(context, mesh_name)
    global image_to_export
    image_to_export = image
    image_node = nodes.new(type="ShaderNodeTexImage")
    image_node.location = node_output.location
    image_node.location.y -= margin
    image_node.image = image
    
    #Set active node
    nodes.active = image_node
    return(mat)

def create_composite(context, image):
    context.scene.use_nodes = True
    composite_nodes = context.scene.node_tree.nodes
    composite_nodes.clear()
    links = context.scene.node_tree.links
    #Node creation
    cnode_output = composite_nodes.new("CompositorNodeViewer")
    cnode_image = composite_nodes.new("CompositorNodeImage")
    cnode_blur = composite_nodes.new("CompositorNodeBlur")
    #Node settings
    cnode_blur.filter_type = 'FAST_GAUSS'
    cnode_blur.use_relative = True
    cnode_blur.factor_y = 5
    cnode_image.image = image
    #Node linking
    links.new(cnode_image.outputs[0], cnode_blur.inputs[0])
    links.new(cnode_blur.outputs[0], cnode_output.inputs[0])
    


class MenuPanel(bpy.types.Panel):
    bl_idname = "paint.gradient_texturing"
    bl_label = "Gradient Texturing"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_category = "Arura"

    def draw(self, context):
        layout = self.layout
        scn = context.scene
        
        col = layout.column(align=False)
        col.label(text="Initialize:")
        row = col.row(align=False)
        row.operator("bake.process_mesh")
        row = layout.row()
        col.label(text="Export Destination:")
        layout.prop(scn, 'file_dir')
        row = layout.row()
        row.operator("bake.export_tex_mesh")
        
        layout.label("Texture Control:")
        row = layout.row()
        ob = context.active_object
        if len(ob.material_slots.items()) > 0:
            ob_mat = ob.material_slots[0]
            try:
                node_col_ramp = ob_mat.material.node_tree.nodes['Color']
                layout.template_color_ramp(node_col_ramp, "color_ramp", expand=True)
            except:
                pass
            try:
                node_val_ramp = ob_mat.material.node_tree.nodes['Value']
                layout.template_color_ramp(node_val_ramp, "color_ramp", expand=True)
            except:
                pass
        
class ProcessMesh(bpy.types.Operator):
    """Unwraps, applies material and adds empty texture"""
    bl_idname = "bake.process_mesh"
    bl_label = "Process Mesh"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        if context.active_object:
            ob = context.active_object
            mesh_name = ob.name
            if ob.mode != 'EDIT':
                bpy.ops.object.editmode_toggle()
            bpy.ops.view3d.viewnumpad(type = 'FRONT')
            bpy.ops.view3d.view_selected()
            bpy.ops.uv.project_from_view(orthographic = True, scale_to_bounds = True)
            bpy.context.space_data.show_only_render = True
            ob.active_material = create_gradient_material(context, mesh_name)
            if ob.mode == 'EDIT':
                bpy.ops.object.editmode_toggle()
            return {'FINISHED'}
        else:
            self.report({'INFO'}, "Select an object to process")
            return {'FINISHED'}

class Export(bpy.types.Operator):
    """Exports both the mesh and texture into selected folder"""
    bl_idname = "bake.export_tex_mesh"
    bl_label = "Export"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        if context.active_object:
            ob = context.active_object
            scn = context.scene
            global image_to_export
            scn.cycles.bake_type = 'DIFFUSE'
            bake_settings = bpy.data.scenes[scn.name].render.bake
            bake_settings.use_pass_color = True
            bake_settings.use_pass_direct = False
            bake_settings.use_pass_indirect = False
            bpy.ops.object.bake(type='DIFFUSE')
            create_composite(context, image_to_export)
            composite_image = bpy.data.images['Viewer Node']
            export_path = bpy.data.scenes[scn.name].file_dir
            self.fbx_export(context, export_path, ob.name)
            composite_image.save_render(export_path + image_to_export.name + ".png")
            return {'FINISHED'}
    
    def fbx_export(self, context, file_dir, name):
        #Reserved for possible presets.
        bpy.ops.export_scene.fbx(filepath = (file_dir + name + ".fbx"), use_selection=True, object_types={'MESH'})
        return {'FINISHED'}

def register():
    bpy.types.Scene.file_dir = StringProperty(name="Path", subtype="FILE_PATH")
    
    bpy.utils.register_class(ProcessMesh)
    bpy.utils.register_class(Export)
    bpy.utils.register_class(MenuPanel)
    
def unregister():
    del bpy.types.Scene.file_dir
    bpy.utils.unregister_class(ProcessMesh)
    bpy.utils.unregister_class(Export)
    bpy.utils.unregister_class(MenuPanel)
    
if __name__ == '__main__':
    register()
            