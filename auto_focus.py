'''
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
'''

bl_info = {
    "name": "Auto Focus",
    "category": "Object",
    "description": "Sets camera to autofocus on narest surface.",
    "author": "Leigh Harborne",
    "version": (0, 3, 0),
    "blender": (2, 7, 9),
    "location": "Properties > Data",
}

import bpy
import math
from bpy.props import (
    FloatProperty,
    BoolProperty,
    PointerProperty,
    CollectionProperty,
    StringProperty,
    )
from bpy.types import (
    Panel,
    PropertyGroup,
    )
from bpy.app.handlers import persistent
from mathutils import Vector
import time

last_time = time.clock()
elapsed = 0.0
        
def create_target(cam):
    target = bpy.data.objects.new("AutoFocus_Target", None)
    target.empty_draw_size = 1
    target.empty_draw_type = "ARROWS"
    target.parent = cam
    cam.data.autofocus.target = target
    cam.data.dof_object = target
        
    bpy.context.scene.objects.link(target)
    
def remove_target(cam):
    target = cam.data.autofocus.target
    
    if cam.data.autofocus.smooth:
        remove_smooth_target(cam)
    
    cam.data.autofocus.target = None
    cam.data.dof_object = None
    target.parent = None
    
    bpy.context.scene.objects.unlink(target)
    
    objs = bpy.data.objects
    objs.remove(objs[target.name])
    
def create_smooth_target(cam):
    target = cam.data.autofocus.target
    smooth = bpy.data.objects.new("AutoFocus_Smooth_Target", None)
    smooth.empty_draw_size = 1
    smooth.empty_draw_type = "CIRCLE"
    smooth.rotation_euler.x = math.radians(90)
    smooth.parent = target
    smooth.use_slow_parent = True
    smooth.slow_parent_offset = cam.data.autofocus.smooth_offset
    
    cam.data.dof_object = smooth
    bpy.context.scene.objects.link(smooth)
    
def remove_smooth_target(cam):
    target = cam.data.autofocus.target
    smooth = target.children[0]
    cam.data.dof_object = target
    smooth.use_slow_parent = False
    smooth.parent = None
    
    bpy.context.scene.objects.unlink(smooth)
    objs = bpy.data.objects
    objs.remove(objs[smooth.name])
    
def find_cam(scn, af):
    for obj in scn.objects:
        if(obj.type=='CAMERA' and obj.data.autofocus != None
        and obj.data.autofocus == af):
            return obj
        
    return None
        
def set_enabled(self, value):
    self["enabled"] = value
    scn = bpy.context.scene
    cam = find_cam(scn, self)
    if value:
        uid = cam.name + str(time.time())
        cam.data.autofocus.uid = uid
        a_cam = scn.autofocus_properties.active_cameras.add()
        a_cam.camera = cam
        a_cam.name = uid
        create_target(cam)
        reset_clock()
    else:
        i = scn.autofocus_properties.active_cameras.find(cam.data.autofocus.uid)
        scn.autofocus_properties.active_cameras.remove(i)
        remove_target(cam)
        cam.data.autofocus.smooth = False
    
def get_enabled(self):
    if self.get("enabled") == None:
        return False
    else:
        return self["enabled"]
    
def set_smooth_enabled(self, value):
    self["smooth"] = value
    scn = bpy.context.scene
    cam = find_cam(scn, self)
    if value:
        create_smooth_target(cam)
    else:
        remove_smooth_target(cam)
    
def get_smooth_enabled(self):
    if self.get("smooth") == None:
        return False
    else:
        return self["smooth"]
    
def set_smooth_offset(self, value):
    self["smooth_offset"] = value
    scn = bpy.context.scene
    cam = find_cam(scn, self)
    cam.data.autofocus.target.children[0].slow_parent_offset = value
    
def get_smooth_offset(self):
    if self.get("smooth_offset") == None:
        return 0.0
    else:
        return self["smooth_offset"]
    
def set_timer_enabled(self, value):
    self["enabled"] = value
    reset_clock()
    
def get_timer_enabled(self):
    if self.get("enabled") == None:
        return False
    else:
        return self["enabled"]
    
class AutoFocus_Properties(PropertyGroup):
    enabled = BoolProperty(
        name="Enabled",
        default=False,
        description="Enable auto focus for this camera.",
        get=get_enabled,
        set=set_enabled
        )
    min = FloatProperty(
        name="Min Distance",
        min=0.0,
        default=0.0,
        description="Minimum focus distance."
        )
    max = FloatProperty(
        name="Max Distance",
        min=0.1,
        default=100.0,
        description="Maximum focus distance."
        )
    smooth = BoolProperty(
        name="Smoothing",
        default=False,
        description="Enable smoothing for auto focus using slow parent.",
        get=get_smooth_enabled,
        set=set_smooth_enabled
        )
    smooth_offset = FloatProperty(
        name="Offset",
        default=1.0,
        description="Offset for smoothing. Higher values mean slower focusing.",
        get=get_smooth_offset,
        set=set_smooth_offset
        )
    uid = StringProperty(
        name="UID",
        default="",
        description="Unique Identifier"
        )
    target = PointerProperty(
        type=bpy.types.Object,
        name="Focus Target",
        description="The object which will be used for DoF focus."
        )
        
class AutoFocus_Active_Camera(PropertyGroup):
    name = ""
    camera = bpy.props.PointerProperty(type=bpy.types.Object)
        
class AutoFocus_Scene_Properties(PropertyGroup):
    active_cameras = CollectionProperty(
        type=AutoFocus_Active_Camera
    )
    rate_enabled = BoolProperty(
        name="Timer",
        default=True,
        description="Enable timer between AutoFocus updates. (Improves performance)",
        get=get_timer_enabled,
        set=set_timer_enabled
        )
    rate_seconds = FloatProperty(
        name="Seconds",
        default=0.5,
        description="The rate in seconds between AutoFocus updates. (Disabled = update on every scene update)"
        )
        
class AutoFocus_Panel(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'
    bl_label = "Auto Focus"
    
    @classmethod
    def poll(cls, context):
        ob = context.object
        return ob and ob.type == 'CAMERA' and context.object.data
    
    def draw_header(self, context):
        af = context.object.data.autofocus
        self.layout.prop(af, "enabled", text="")
    
    def draw(self, context):
        af = context.object.data.autofocus
        layout = self.layout
        
        labels = layout.split(percentage=0.5)
        labels.label("Min Distance:")
        labels.label("Max Distance:")
        
        split = layout.split(percentage=0.5)
        split.active = af.enabled
        split.prop(af, "min", text="")
        split.prop(af, "max", text="")
        
        row = layout.row()
        row.active = af.enabled
        row.prop(af, "smooth")
        row = layout.row()
        row.enabled = af.smooth
        row.prop(af, "smooth_offset")
        
        split = layout.split(percentage=0.5)
        split.prop(context.scene.autofocus_properties, "rate_enabled")
        split.prop(context.scene.autofocus_properties, "rate_seconds")
    
@persistent
def scene_update(scn):
    
    if scn.autofocus_properties.rate_enabled and not check_clock(scn):
        return

    for c in scn.autofocus_properties.active_cameras:
        cam = c.camera
        #Set the position of the target empties.
        af = cam.data.autofocus
        tgt_loc = af.target.location
        
        if af.max <= af.min:
            af.max = af.min + 0.01
        
        cam_matrix = cam.matrix_world
        org = cam_matrix * Vector((0.0, 0.0, af.min * -1))
        dst = cam_matrix * Vector((0.0, 0.0, af.max * -1))
        dir = dst - org

        result, location, normal, index, object, matrix = scn.ray_cast(org, dir, dir.length)
        
        if result:
            new_loc = cam.matrix_world.inverted() * location
            
            tgt_loc.x = new_loc.x
            tgt_loc.y = new_loc.y            
            tgt_loc.z = new_loc.z
            
        if tgt_loc.z * -1 > af.max:
            tgt_loc.z = af.max * -1
        if tgt_loc.z * -1 < af.min:
            tgt_loc.z = af.min * -1
        
def check_clock(scn):
    global last_time
    global elapsed
    cur_time = time.clock()
    
    elapsed += cur_time - last_time
    last_time = cur_time
    
    if elapsed >= scn.autofocus_properties.rate_seconds:
        elapsed = 0.0
        return True
    
    return False

def reset_clock():
    global last_time
    global elapsed
    last_time = time.clock()
    elapsed = 0.0
        
def register():
    bpy.utils.register_class(AutoFocus_Panel)
    bpy.utils.register_class(AutoFocus_Properties)
    bpy.utils.register_class(AutoFocus_Active_Camera)
    bpy.utils.register_class(AutoFocus_Scene_Properties)
    bpy.types.Camera.autofocus = PointerProperty(
                                    type=AutoFocus_Properties
                                    )
    bpy.types.Scene.autofocus_properties = PointerProperty(
                                    type=AutoFocus_Scene_Properties
                                    )
    bpy.app.handlers.scene_update_post.append(scene_update)

def unregister():
    bpy.utils.unregister_class(AutoFocus_Panel)
    bpy.utils.unregister_class(AutoFocus_Properties)
    bpy.utils.unregister_class(AutoFocus_Active_Camera)
    bpy.utils.unregister_class(AutoFocus_Scene_Properties)
    bpy.app.handlers.scene_update_post.remove(scene_update)
    del bpy.types.Camera.autofocus
    del bpy.types.Scene.autofocus_properties
    
if __name__ == "__main__":
    register()
