from os.path import exists
from pathlib import Path
from zipfile import ZipFile
import bpy

def extract(zipfile, name, dest):
    zf = zipfile + '.zip'
    with ZipFile(zf) as z:
        z.extract(name, dest)
    
def load_materials(library, material_name):
    with bpy.data.libraries.load(library) as (source, target):
        names = sorted(
            name for name in source.materials
            if name.startswith(material_name)
        )
        # Blender resolves this list in place; preserve the original names as keys.
        target.materials = names.copy()

    if not names or not all(target.materials):
        raise ValueError(f"Cannot load {material_name} from {library}")

    return dict(zip(names, target.materials))


def load_particlesettings(library, object_name):
    with bpy.data.libraries.load(library) as (source, target):
        if not any(name.startswith(object_name) for name in source.objects):
            raise ValueError(f"No {object_name} objects in {library}")
        names = sorted(source.particles)
        target.particles = names.copy()
    if not names or not all(target.particles):
        raise ValueError(f"No complete particle preset set in {library}")
    return dict(zip(names, target.particles))

def load_materials_from_bundled_lib(script_name, library, material_name):
    """Load a material from a library located in the installation directory of a script.""" 
    fullpath = str(Path(__file__).resolve().parent / library)
    if not exists(fullpath) and exists(fullpath + ".zip"):
        extract(fullpath, library, str(Path(fullpath).parent))
    return load_materials(fullpath, material_name)

def load_particlesettings_from_bundled_lib(script_name, library, object_name):
    """Load particle settings associated with objects from a library located in the installation directory of a script.""" 
    fullpath = str(Path(__file__).resolve().parent / library)
    if not exists(fullpath) and exists(fullpath + ".zip"):
        extract(fullpath, library, str(Path(fullpath).parent))
    return load_particlesettings(fullpath, object_name)

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
 
