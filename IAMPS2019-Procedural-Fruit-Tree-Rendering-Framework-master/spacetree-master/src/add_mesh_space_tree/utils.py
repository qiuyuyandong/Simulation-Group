from os import remove
from os.path import exists, join
from zipfile import ZipFile
import bpy

def extract(zipfile, name, dest):
    zf = zipfile + '.zip'
    with ZipFile(zf) as z:
        z.extract(name, dest)
    remove(zf)
    
def load_materials(library, material_name):
    with bpy.data.libraries.load(library) as (source, target):
        names = sorted(
            name for name in source.materials
            if name.startswith(material_name)
        )
        target.materials = names.copy()

    if not names or not all(target.materials):
        raise ValueError(f"Cannot load {material_name} from {library}")

    return dict(zip(names, target.materials))
    
def load_particlesettings(library, object_name):
    beforep = set(m.name for m in bpy.data.particles)
    before  = set(m.name for m in bpy.data.objects)
    with bpy.data.libraries.load(library) as (data_from, data_to):
        data_to.objects = [m for m in data_from.objects if m.startswith(object_name)]
    afterp = set(m.name for m in bpy.data.particles)
    after = set(m.name for m in bpy.data.objects)
    new = after - before
    if len(new) < 1:
        raise ValueError("While loading objects with names starting with %s from library %s 0 objects were found"%(
            object_name,library))
    new = afterp - beforep
    if len(new) < 1:
        raise ValueError("While loading particle settings from objects with names starting with %s from library %s no particle settings were found"%(object_name,library))
    return {p:bpy.data.particles[p] for p in new}
    
def load_materials_from_bundled_lib(script_name, library, material_name):
    """Load a material from a library located in the installation directory of a script.""" 
    for dir in ('addons','addons_contrib'):
        for path in bpy.utils.script_paths():
            fullpath = join(path, dir, script_name, library)
            if exists(fullpath):
                return load_materials(fullpath, material_name)
            if exists(fullpath + ".zip"):
                extract(fullpath, library, join(path, dir, script_name))
                return load_materials(fullpath, material_name)
    return None

def load_particlesettings_from_bundled_lib(script_name, library, object_name):
    """Load particle settings associated with objects from a library located in the installation directory of a script.""" 
    for dir in ('addons','addons_contrib'):
        for path in bpy.utils.script_paths():
            fullpath = join(path, dir, script_name, library)
            if exists(fullpath):
                return load_particlesettings(fullpath, object_name)
            if exists(fullpath + ".zip"):
                extract(fullpath, library, join(path, dir, script_name))
                return load_particlesettings(fullpath, object_name)
    return None

def get_vertex_group(context, name):
    """Get a reference to the named vertex group of the active object, creating it if necessary."""
    ob = context.active_object
    if ob is None :
        return None
    if name in ob.vertex_groups:
        return ob.vertex_groups[name]
    else:
        bpy.ops.object.vertex_group_add()
        vg = ob.vertex_groups.active
        vg.name = name
        return vg
 