import bpy



def min_vertex(mesh, axis):
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

def create_mat(name):
    """Returns a material and the output node of that material"""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    out_node = mat.node_tree.nodes['Diffuse BSDF']
    out_node.name = 'out'
    
    return mat, out_node

def create_img(name, width, height):
    """Returns an image type"""
    img = bpy.data.images.new(name, width, height)
    
    return img
    

def ao_mask(mask):
    """Returns an image with a baked Ambient Occlusion"""
    mask['mat'].node_tree.nodes.active = mask['image_node']
    bpy.ops.object.bake('INVOKE_DEFAULT', type='AO')
        
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
    bpy.ops.object.bake('INVOKE_DEFAULT', type='DIFFUSE')

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
        if ob.mode != 'EDIT':
            bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.subdivide()
        bpy.ops.object.editmode_toggle()

    if ob.mode != 'OBJECT':
        bpy.ops.object.editmode_toggle()

    nodes = mask['mat'].node_tree.nodes
    #Nodes Creation
    geo = nodes.new("ShaderNodeNewGeometry")
    #Nodes linking
    links = mask['mat'].node_tree.links
    links.new(geo.outputs[7], mask['output'].inputs[0])
    #Baking
    mask['mat'].node_tree.nodes.active = mask['image_node']
    enable_color_bake_settings()
    bpy.ops.object.bake('INVOKE_DEFAULT', type='DIFFUSE')
    bpy.ops.object.delete()

    return mask['image']

def get_mask(context, resolution, map_type):
    """Returns an image with a baked map depending on the 'type' parameter"""
    mask = {}
    if context.active_object:
        ob = context.active_object
        if ob.active_material:
            original_mat = ob.active_material #Might want to handle this!
            has_mat = True
        else:
            has_mat = False
        mask['mat'], mask['output'] = create_mat(''.join(['mask_', map_type])) #Output is actually a BSDF node
        ob.active_material = mask['mat']
        mask['image_node'] = mask['mat'].node_tree.nodes.new("ShaderNodeTexImage")
        mask['image'] = create_img(''.join([ob.name, '_', map_type]), resolution[0], resolution[1])
        mask['image_node'].image = mask['image']

        if map_type == 'AO':
            img_mask = ao_mask(mask)
        elif map_type == 'POS':
            img_mask = position_mask(context, mask)
        elif map_type == 'CURVE':
            img_mask = curvature_mask(context, mask)
        if has_mat:
            #ob.active_material = original_mat
        #bpy.data.materials.remove(mask['mat'], do_unlink=True)
        return img_mask
    else:
        self.report({'WARNING'}, "No active selection!")
        return {'FINISHED'}

class BakePosition(bpy.types.Operator):
    bl_idname = "bake.position_mask"
    bl_label = "Pre-Process Mesh"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        resolution = [1024, 1024]
        pos_mask = get_mask(context, resolution, 'POS')
        #curve_mask = get_mask(context, resolution, 'CURVE')
        return {'FINISHED'}

class BakeAO(bpy.types.Operator):
    bl_idname = "bake.ao_mask"
    bl_label = "AO"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        resolution = [1024, 1024]
        ao_mask = get_mask(context, resolution, 'AO')
        return {'FINISHED'}
    
def register():
    bpy.utils.register_class(BakeAO)
    bpy.utils.register_class(BakePosition)
    
def unregister():
    bpy.utils.unregister_class(BakeAO)
    bpy.utils.unregister_class(BakePosition)

if __name__ == '__main__':
    register()