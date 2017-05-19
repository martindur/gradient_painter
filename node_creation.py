import bpy

def create_mat(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    out_node = mat.node_tree.nodes['Diffuse BSDF']
    out_node.name = 'out'
    
    return mat, out_node

def create_img(name, width, height):
    img = bpy.data.images.new(name, width, height)
    
    return img
    

def get_ao_mask(context, resolution):
    if context.active_object:
        ob = context.active_object
        if ob.active_material:
            original_mat = ob.active_material
        mat, output = create_mat('tmp_ao')
        ob.active_material = mat

        img_node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        ao_mask = create_img(ob.name + "_ao", resolution[0], resolution[1])
        img_node.image = ao_mask
        mat.node_tree.nodes.active = img_node
        bpy.ops.object.bake('INVOKE_DEFAULT', type='AO')
        self.report({'INFO'}, "Finished baking Ambient Occlusion map")
        
        return ao_mask
    else:
        self.report({'WARNING'}, "No active object selected. Cancelling..")
        return {'FINISHED'}

def get_position_mask()
