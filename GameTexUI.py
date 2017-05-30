import bpy

DRAWLIST = []



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
                        self.draw_node(node)
        
def register():
    bpy.utils.register_class(WidgetUI)
    
def unregister():
    bpy.utils.unregister_class(WidgetUI)
    
if __name__ == '__main__':
    register()