bl_info = {
    "name": "Task Tracker",
    "blender": (2, 80, 0),
    "category": "Tools",	
    "version": (0, 1, 0),
    "author":"Gorgious56",
    "description":"Task tracker in the World properties. Supports parenting relationships and editing task names and times.",
}

import atexit
from time import time

import bpy
from bpy.app.handlers import persistent
from bpy.props import (
    IntProperty,
   BoolProperty,
   StringProperty,
   CollectionProperty,
   PointerProperty,
   FloatProperty,
)

from bpy.types import (
    Operator,
    Panel,
    PropertyGroup,
    UIList,
    World,
)

# https://gist.github.com/p2or/30b8b30c89871b8ae5c97803107fd494


def stop_tracking():
    bpy.context.scene.world.tt_props.global_tracking = False

@persistent
def update_tracking_handler(dummy):
    bpy.context.scene.world.tt_props.global_tracking = 0
    bpy.ops.task_tracker.track_tasks('INVOKE_DEFAULT')

def update_tracking(self, context):
    tasks = context.scene.world.tt_tasks
    
    if self.is_tracking:
        bpy.ops.task_tracker.track_tasks('INVOKE_DEFAULT')
        tasks_dic = {-1 : None}
        for task in tasks:
            tasks_dic[task.id] = task
        
        def track_childs(task, family):
            for child in task.childs:
                task_child = tasks_dic[child.id]
                family.append(task_child)
                track_childs(task_child, family)
        
        if self is not None:
            root = self
            while root.parent >= 0:
                root = tasks_dic[root.parent]
                
            family = [root]
            track_childs(root, family)
            for t in family:
                if t == self:
                    continue
                t.is_tracking = False

def update_task_tracker_index(self, context):
    tasks = context.world.tt_tasks
    index = self.index
    if not tasks:
        return
    elif index < 0:
        index = 0
    elif index >= len(tasks):
        index = len(tasks) - 1


#def update_builtins(self, context):
#    tasks = context.world.tt_tasks
#    props = context.world.tt_props
#    workspaces_names = [ws.name for ws in bpy.data.workspaces]
#    for task in tasks[:]:
#        if not task.builtin:
#            continue
#        if task.name in workspaces_names:
#            workspaces_names.remove(task.name)
#        else:
#            tasks.remove(tasks.index(task))
#    for ws_name in workspaces_names:        
#        item = tasks.add()
#        item.id = props.global_index # TODO : increment on get ?
#        props.global_index += 1  
#        item.name = ws_name
#        item.builtin = True
#        props.index = len(tasks) - 1


def get_child_times(self):
    time = 0
    child_ids = [child.id for child in self.childs]
    for task in bpy.context.scene.world.tt_tasks:
        if task.id in child_ids:
            time += task.time_total
    return time

class TaskChilds(PropertyGroup):
    id: IntProperty(default=-1)

class TaskTrackerTasks(PropertyGroup):
    id: IntProperty()
    parent: IntProperty(default=-1)
    childs: CollectionProperty(type=TaskChilds)
    name: StringProperty(maxlen=256)
    time: FloatProperty(min=0, precision=0, subtype='TIME', unit='TIME')
    time_childs: FloatProperty(min=0, precision=0, subtype='TIME', unit='TIME', get=get_child_times)
    time_total: FloatProperty(min=0, precision=0, subtype='TIME', unit='TIME', get=lambda self: self.time + self.time_childs)
    is_tracking: BoolProperty(description="Track this task", update=update_tracking)
    builtin: BoolProperty(default=False)


class TaskTrackerProps(PropertyGroup):
    index: IntProperty(update=update_task_tracker_index)
    global_tracking: BoolProperty()
    global_index: IntProperty(default=1)
    edit_times: BoolProperty()
    show_builtins: BoolProperty(default=False, update=update_builtins)


class TASK_TRACKER_OT_Actions(Operator):
    """Move items up and down, add and remove"""
    bl_idname = "custom.list_action"
    bl_label = "List Actions"
    bl_description = "Move items up and down, add and remove"
    bl_options = {'REGISTER', 'UNDO'}

    action: bpy.props.EnumProperty(
        items=(
            ('UP', "Up", ""),
            ('DOWN', "Down", ""),
            ('REMOVE', "Remove", ""),
            ('ADD', "Add", ""),
            ('PARENT', "Parent", ""),
            ))

    def invoke(self, context, event):
        world = context.scene.world
        tasks = world.tt_tasks
        props = world.tt_props
        idx = props.index
        
        if self.action == 'DOWN':
            if idx < len(tasks) - 1:
                item_next = tasks[idx + 1].name
                tasks.move(idx, idx+1)
                props.index += 1

        elif self.action == 'UP':
            if idx >= 1:
                item_prev = tasks[idx - 1].name
                tasks.move(idx, idx - 1)
                props.index -= 1

        elif self.action == 'REMOVE':
            if 0 <= idx < len(tasks):
                this_task = tasks[idx]
                child_indices = [c.id for c in tasks[idx].childs]
                for task in tasks:
                    if task.id in child_indices:
                        task.parent = this_task.parent
                tasks.remove(idx)
                props.index = max(0, idx - 1)

        elif self.action == 'ADD':
            item = tasks.add()
            item.id = props.global_index
            item.name = "Task " + str(item.id)
            tasks.move(len(tasks) - 1, idx + 1)
            props.index = idx + 1    
            props.global_index += 1

        elif self.action == 'PARENT':
            if 0 < idx < len(tasks):
                parent = tasks[idx - 1]
                task = tasks[idx]
                if task.parent >= 0: # Un-parent      
                    task.parent = -1
                    for i, c in enumerate(parent.childs):
                        if c.id == task.id:
                            parent.childs.remove(i)
                            break
                else:
                    task.parent = parent.id
                    child = parent.childs.add()
                    child.id = task.id
                update_tracking(task, context)
            
        return {"FINISHED"}


class TASK_TRACKER_OT_ClearList(Operator):
    """Clear all Trackers from current world"""
    bl_idname = "task_tracker.clear_list"
    bl_label = "Clear All Tasks"
    bl_description = "Clear all tasks"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bool(context.scene.world.tt_tasks)

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        tasks = context.scene.world.tt_tasks
        if tasks:
            tasks.clear()
            self.report({'INFO'}, "All Tasks removed")
        else:
            self.report({'INFO'}, "Nothing to remove")
        return{'FINISHED'}


class TASK_TRACKER_OT_Track(bpy.types.Operator):
    """Operator which runs its self from a timer"""
    bl_idname = "task_tracker.track_tasks"
    bl_label = "Track Tasks"

    _timer = None
    _interval = 1.0
    _last_time = 0.0
    
    @classmethod
    def poll(cls, context):
        return hasattr(context, "scene") and hasattr(context.scene, "world") and hasattr(context.scene.world, "tt_tasks")

    def modal(self, context, event):
        world = context.scene.world
        if not hasattr(world, "tt_props"):
            self.cancel(context)
            return {'CANCELLED'}   

        if event.type == 'TIMER':
            cur_time = time()
            delta_time = cur_time - self._last_time
            for task in world.tt_tasks:
                task.time += delta_time * int(task.is_tracking) / 60
            self._last_time = cur_time
            if context.area:
                context.area.tag_redraw()
        
        return {'PASS_THROUGH'}

    def execute(self, context):
        world = context.scene.world
        
        if world.tt_props.global_tracking:
            return {'CANCELLED'}
        world.tt_props.global_tracking = True         
        wm = context.window_manager
        self._last_time = time()
        self._timer = wm.event_timer_add(self._interval, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        wm = context.window_manager
        wm.event_timer_remove(self._timer)


class TASK_TRACKER_UL_items(UIList):
    def draw_item(self, context, layout, data, task, icon, active_data, active_propname):
        
        props = context.scene.world.tt_props
        if props.show_builtins or not task.builtin:
            split = layout.split(factor=0.5)
            time = task.time_total * 60
            strtime = ""
            days = int(time // 86400)
            if time > 86399:
                strtime += str(days) + "d "
            hours = int((time % 86400) // 3600)
            if time > 3600:
                strtime += ("0" if hours < 10 else "") + str(hours) + "h "
            minutes = int(time % 3600 // 60)
            if time > 60:
                strtime += ("0" if minutes < 10 else "") + str(minutes) + '" '
            seconds = int(time % 60)
            strtime += ("0" if seconds < 10 else "") + str(seconds) + "'"
            
            row = split.row()
            parent_id = task.parent
            if task.parent >= 0:
                for t in context.world.tt_tasks:
                    if t.id == parent_id:
                        row.label(text=t.name, icon='FILE_PARENT')
                        break

#            if task.builtin:
#                row.prop(bpy.data.workspaces[task.name], "name", text="" , emboss=False)
#            else:
            row.prop(task, "name", text="", emboss=False)
            
            if props.edit_times:
                split.prop(task, "time", text="Minutes:", emboss=False)            
            else:
                split.label(text=strtime)
            split = split.split()
            split.prop(task, "is_tracking", text="", toggle=True, icon='TIME')
#            split.enabled = not task.builtin


class TaskTrackerPanel(Panel):
    """Creates a Panel in the World context of the properties editor"""
    bl_label = "Task Tracker"
    bl_idname = "TASK_TRACKER_PT_layout"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "world"    

    def draw(self, context):
        layout = self.layout
        world = context.scene.world
        props = world.tt_props
        tasks = world.tt_tasks

        rows = 2
        row = layout.row()
        row.template_list(
            "TASK_TRACKER_UL_items", 
            "custom_def_list", 
            world, 
            "tt_tasks", 
            props, 
            "index", 
            rows=rows)

        col = row.column(align=True)
        col.operator("custom.list_action", icon='ADD', text="").action = 'ADD'
        col.operator("custom.list_action", icon='REMOVE', text="").action = 'REMOVE'
        col.separator()
        col.prop(world.tt_props, "edit_times", icon='GREASEPENCIL', icon_only=True, toggle=True)
        
        index = props.index
        depress = (tasks[index].parent >= 0) if 0 <= index < len(tasks) else False
        sub_col = col.column(align=True)
        sub_col.operator("custom.list_action", icon='FILE_PARENT', text="", depress=depress).action = 'PARENT'
        sub_col.enabled = index > 0
            
#        col.prop(world.tt_props, "show_builtins", icon='FILE_BLEND', icon_only=True, toggle=True)
        col.separator()
        col.operator("custom.list_action", icon='TRIA_UP', text="").action = 'UP'
        col.operator("custom.list_action", icon='TRIA_DOWN', text="").action = 'DOWN'

        row = layout.row()
        col = row.column(align=True)
        row = col.row(align=True)
        row.operator(TASK_TRACKER_OT_ClearList.bl_idname, icon="X")


classes = (
    TASK_TRACKER_OT_Track,
    TASK_TRACKER_OT_Actions,
    TASK_TRACKER_OT_ClearList,
    TASK_TRACKER_UL_items,
    TaskTrackerPanel,
    TaskTrackerProps,
    TaskChilds,
    TaskTrackerTasks,
    )    


def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
    
    World.tt_tasks = bpy.props.CollectionProperty(type=TaskTrackerTasks)
    World.tt_props = bpy.props.PointerProperty(type=TaskTrackerProps)
    
    bpy.app.handlers.load_post.append(update_tracking_handler)
    atexit.register(stop_tracking)

def unregister():
    atexit.unregister(stop_tracking)
    bpy.app.handlers.load_post.remove(update_tracking_handler) 

    del World.tt_tasks
    del World.tt_props
    
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)
         

if __name__ == "__main__":
    register()
