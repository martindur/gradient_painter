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
import mask_baking as mb
import gp_utils as gp
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
    
def smart_uv_project():
    bpy.ops.uv.smart_project(angle_limit=66,
                             island_margin=0.02,
                             user_area_weight=0,
                             use_aspect=False,
                             stretch_to_bounds=True
                             )

def handle_projection(context):
    if len(context.object.data.uv_textures) == 0:
        uv_map = uv_textures.new()
        smart_uv_project()
        

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

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        if self.poll(context):
            ob = context.active_object
            mesh_name = ob.name
            gp.check_id(context, ob)
            if ob.mode != 'EDIT':
                bpy.ops.object.editmode_toggle()
            handle_projection(context)
            self.check_materials(context, ob, mesh_name)
            if ob.mode == 'EDIT':
                bpy.ops.object.editmode_toggle()
            return {'FINISHED'}
        else:
            self.report({'INFO'}, "Select an object to process")
            return {'CANCELLED'}

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
            