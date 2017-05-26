import bpy

def min_vertex(mesh, axis):
    for i, vt in enumerate(mesh.vertices):
        v = eval('.'.join(['vt.co', axis]))
        if i == 0:
            min = v
        if v < min:
            min = v
    return min

def get_item(context, item, ob, mask=None):
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
                if img['ID'] == ob['ID'] and img['mask'] == mask:
                    return img
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

def get_img(ob, name, width, height):
    """Returns an image type"""
    img = get_item(bpy.context, 'IMG', ob)
    if img is None:
        img = bpy.data.images.new(name, width, height)
        img.use_fake_user = True
        img.pack(as_png=True)
        img['ID'] = ob['ID']
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
        ob['ID'] += max(ob_IDs)