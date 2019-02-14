# Copyright (C) 2019 h0bB1T
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
#
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301  USA

import bpy
from bpy.types import Operator
from bpy.props import StringProperty

from . nw_node_utils import NW_NodeUtils

class NW_NormalScalerOperator(Operator, NW_NodeUtils):
    bl_idname = "material.nw_normal_scaler_op"
    bl_label = "Create Normal Scaler"
    bl_description = "Generates a setup to scale a normal and plugs it to the Normal output of all selected nodes."
    bl_options = {'REGISTER', 'UNDO'}

    def fill_normal_scaler(self, group, input, output):
        tree = group.node_tree

        separate = self.at(tree.nodes.new("ShaderNodeSeparateXYZ"), 1, 0)
        mul = self.at(self.create_math_node(tree, "MULTIPLY"), 2, -1)
        combine = self.at(tree.nodes.new("ShaderNodeCombineXYZ"), 3, 0)
        norm = self.at(tree.nodes.new("ShaderNodeVectorMath"), 4, 0)
        norm.operation = "NORMALIZE"

        tree.links.new(separate.outputs["X"], combine.inputs["X"])
        tree.links.new(separate.outputs["Y"], combine.inputs["Y"])
        tree.links.new(separate.outputs["Z"], mul.inputs[0])
        tree.links.new(mul.outputs["Value"], combine.inputs["Z"])
        tree.links.new(combine.outputs["Vector"], norm.inputs[0])

        tree.links.new(self.create_group_input(group, input, "Vector", "Vector"), separate.inputs["Vector"])
        tree.links.new(self.create_group_input(group, input, "Float", "Scale", 1.0), mul.inputs[1])
        tree.links.new(norm.outputs["Vector"], self.create_group_output(group, output, "Vector", "Vector"))

    def execute(self, context):
        # Access the current tree.
        tree = context.space_data.edit_tree

        validNodes = self.get_selected_nodes_with_output(tree, "Normal")
        if not validNodes:
            self.report({"ERROR"}, "No node with Normal output selected.")
            return{'CANCELLED'}

        for candidate in validNodes:
            # Create a node for this one.
            group, input, output = self.create_group(tree, "NW Normal Scaler", 5)
            group.location = candidate.location.x + self.gridSizeX, candidate.location.y
            self.fill_normal_scaler(group, input, output)

            # Rebuild mapping.
            self.remap_output_links(tree, candidate, "Normal", group, "Vector")
            tree.links.new(candidate.outputs["Normal"], group.inputs["Vector"])

        return{'FINISHED'}

class NW_DX2OGLConverterOperator(Operator, NW_NodeUtils):
    bl_idname = "material.nw_dx2ogl_converter_op"
    bl_label = "Create DX2OGL Normal Converter"
    bl_description = "Generates a setup to convert DirectX normal maps to OpenGL(Blender) normal maps and plugs it to the Color output of all selected nodes."
    bl_options = {'REGISTER', 'UNDO'}

    def fill_dx2ogl_converter(self, group, input, output):
        tree = group.node_tree

        separate = self.at(tree.nodes.new("ShaderNodeSeparateXYZ"), 1, 0)
        sub = self.at(self.create_math_node(tree, "SUBTRACT", def0 = 1.0), 2, -1)
        combine = self.at(tree.nodes.new("ShaderNodeCombineXYZ"), 3, 0)

        tree.links.new(separate.outputs["X"], combine.inputs["X"])
        tree.links.new(separate.outputs["Y"], sub.inputs[1])
        tree.links.new(sub.outputs["Value"], combine.inputs["Y"])
        tree.links.new(separate.outputs["Z"], combine.inputs["Z"])

        tree.links.new(self.create_group_input(group, input, "Vector", "Vector"), separate.inputs["Vector"])
        tree.links.new(combine.outputs["Vector"], self.create_group_output(group, output, "Vector", "Vector"))

    def execute(self, context):
        # Access the current tree.
        tree = context.space_data.edit_tree

        validNodes = self.get_selected_nodes_with_output(tree, "Color")
        if not validNodes:
            self.report({"ERROR"}, "No node with Color output selected.")
            return{'CANCELLED'}

        for candidate in validNodes:
            # Create a node for this one.
            group, input, output = self.create_group(tree, "NW DX 2 OGL Converter", 5)
            group.location = candidate.location.x + self.gridSizeX, candidate.location.y
            self.fill_dx2ogl_converter(group, input, output)

            # Rebuild mapping.
            self.remap_output_links(tree, candidate, "Color", group, "Vector")
            tree.links.new(candidate.outputs["Color"], group.inputs["Vector"])

        return{'FINISHED'}      

class NW_GenerateTwoLayerTextureBasedSetupOperator(Operator, NW_NodeUtils):
    bl_idname = "material.nw_generate_two_layer_texture_based_setup_op"
    bl_label = "Two Layers, Texture based"
    bl_description = "Generates setup that mixes two selected material nodes using a mask and adds a height shift between both (Texture based)."
    bl_options = {'REGISTER', 'UNDO'}

    def create_optional_mix(self, tree, gridX, gridY, nodes, name, factorSocket, targetSocket, defValue):
        # expected to be 2 entries ...
        n0 = nodes[0].outputs[name] if nodes[0].outputs.find(name) != -1 else None
        n1 = nodes[1].outputs[name] if nodes[1].outputs.find(name) != -1 else None
        
        if n0 or n1:
            mix = self.at(tree.nodes.new("ShaderNodeMixRGB"), gridX, gridY)
            tree.links.new(factorSocket, mix.inputs["Fac"])
            if targetSocket:
                tree.links.new(mix.outputs["Color"], targetSocket)
            if n0:
                tree.links.new(n0, mix.inputs[1])
            else: 
                mix.inputs[1].default_value = defValue
            if n1:
                tree.links.new(n1, mix.inputs[2])
            else: 
                mix.inputs[2].default_value = defValue
            return mix.outputs["Color"]

        return None

    def execute(self, context):
        # Access the current tree.
        tree = context.space_data.edit_tree

        selected = self.get_selected_nodes(tree)
        if len(selected) != 2:
            self.report({"ERROR"}, "Select two generated materials.")
            return{'CANCELLED'}

        if selected[0].location.y > selected[1].location.y:
            self.baseX, self.baseY = selected[0].location.x + self.gridSizeX, selected[0].location.y - self.gridSizeY
        else:
            self.baseX, self.baseY = selected[1].location.x + self.gridSizeX, selected[1].location.y - self.gridSizeY

        noise = self.at(tree.nodes.new("ShaderNodeTexNoise"), -2, 0)
        ramp = self.at(tree.nodes.new("ShaderNodeValToRGB"), 0, 0)
        ramp.color_ramp.elements[0].position = 0.499
        ramp.color_ramp.elements[1].position = 0.501
        tree.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
        bump = self.at(tree.nodes.new("ShaderNodeBump"), 2, 0)
        tree.links.new(ramp.outputs["Color"], bump.inputs["Height"])
        shader = self.at(tree.nodes.new("ShaderNodeBsdfPrincipled"), 7, 0)

        gridY = 2
        if self.create_optional_mix(tree, 3, gridY, selected, "Base Color", ramp.outputs["Color"], shader.inputs["Base Color"], (0.8, 0.8, 0.8, 0)): gridY -= 1
        if self.create_optional_mix(tree, 3, gridY, selected, "Metallic", ramp.outputs["Color"], shader.inputs["Metallic"], (0, 0, 0, 0)): gridY -= 1
        if self.create_optional_mix(tree, 3, gridY, selected, "Specular", ramp.outputs["Color"], shader.inputs["Specular"], (0.5, 0.5, 0.5, 0)): gridY -= 1
        if self.create_optional_mix(tree, 3, gridY, selected, "Roughness", ramp.outputs["Color"], shader.inputs["Roughness"], (0.5, 0.5, 0.5, 0)): gridY -= 1
        
        normal = self.create_optional_mix(tree, 3, gridY, selected, "Normal", ramp.outputs["Color"], None, (0.0, 0.0, 1, 0))
        if normal:
            geom = self.at(tree.nodes.new("ShaderNodeNewGeometry"), 4, 2)
            vmath = self.at(tree.nodes.new("ShaderNodeVectorMath"), 5, 1)
            mixNormal = self.at(tree.nodes.new("ShaderNodeMixRGB"), 6, 0)
            vmath.operation = "DOT_PRODUCT"
            tree.links.new(geom.outputs["Normal"], vmath.inputs[0])
            tree.links.new(bump.outputs["Normal"], vmath.inputs[1])
            tree.links.new(vmath.outputs["Value"], mixNormal.inputs["Fac"])
            tree.links.new(bump.outputs["Normal"], mixNormal.inputs[1])
            tree.links.new(normal, mixNormal.inputs[2])
            tree.links.new(mixNormal.outputs["Color"], shader.inputs["Normal"])
        else:
            tree.links.new(bump.outputs["Normal"], shader.inputs["Normal"])

        return{'FINISHED'}   

class NW_GenerateTwoLayerShaderBasedSetupOperator(Operator, NW_NodeUtils):
    bl_idname = "material.nw_generate_two_layer_shader_based_setup_op"
    bl_label = "Two Layers, Shader based"
    bl_description = "Generates setup that mixes two selected material nodes using a mask and adds a height shift between both (Shader based)."
    bl_options = {'REGISTER', 'UNDO'}   

    def create_layer_group(self, baseTree):
        group, input, output = self.create_group(baseTree, "NW Shader Layer", 5)
        tree = group.node_tree

        bump = self.at(tree.nodes.new("ShaderNodeBump"), 0, 0)
        shader = self.at(tree.nodes.new("ShaderNodeBsdfPrincipled"), 2, 0)
        geom = self.at(tree.nodes.new("ShaderNodeNewGeometry"), 1, 2)
        mix0 = self.at(tree.nodes.new("ShaderNodeMixShader"), 1, 0)
        dot = self.at(tree.nodes.new("ShaderNodeVectorMath"), 2, 1)
        dot.operation = "DOT_PRODUCT"
        mix1 = self.at(tree.nodes.new("ShaderNodeMixShader"), 4, 0)

        tree.links.new(self.create_group_input(group, input, "Shader", "Shader Lower"), mix0.inputs[1])
        tree.links.new(self.create_group_input(group, input, "Shader", "Shader Upper"), mix0.inputs[2])
        mask = self.create_group_input(group, input, "Float", "Mask")
        tree.links.new(mask, mix0.inputs["Fac"])
        tree.links.new(mask, bump.inputs["Height"])

        tree.links.new(geom.outputs["Normal"], dot.inputs[0])
        tree.links.new(bump.outputs["Normal"], dot.inputs[1])
        tree.links.new(bump.outputs["Normal"], shader.inputs["Normal"])
        tree.links.new(dot.outputs["Value"], mix1.inputs["Fac"])
        tree.links.new(shader.outputs["BSDF"], mix1.inputs[1])
        tree.links.new(mix0.outputs["Shader"], mix1.inputs[2])
        tree.links.new(mix1.outputs["Shader"], self.create_group_output(group, output, "Shader", "Shader"))

        tree.links.new(self.create_group_input(group, input, "Color", "Gap Base Color", (1, 0, 0, 1)), shader.inputs["Base Color"])
        tree.links.new(self.create_group_input(group, input, "Float", "Gap Metallic", 0.0), shader.inputs["Metallic"])
        tree.links.new(self.create_group_input(group, input, "Float", "Gap Specular", 0.5), shader.inputs["Specular"])
        tree.links.new(self.create_group_input(group, input, "Float", "Gap Roughness", 0.5), shader.inputs["Roughness"])
        tree.links.new(self.create_group_input(group, input, "Float", "Gap Height", 1.0), bump.inputs["Strength"])

        return (group, input, output)

    def execute(self, context):
        # Access the current tree.
        tree = context.space_data.edit_tree

        # What to mix up.
        selected = self.get_selected_nodes_with_output(tree, "Shader")
        if len(selected) != 2:
            self.report({"ERROR"}, "Select two nodes with Shader output.")
            return{'CANCELLED'}

        # Where to place the nodes.
        if selected[0].location.y > selected[1].location.y:
            self.baseX, self.baseY = selected[0].location.x + self.gridSizeX, selected[0].location.y - self.gridSizeY
        else:
            self.baseX, self.baseY = selected[1].location.x + self.gridSizeX, selected[1].location.y - self.gridSizeY

        group, input, output = self.create_layer_group(tree)
        self.at(group, 2, 0)

        noise = self.at(tree.nodes.new("ShaderNodeTexNoise"), -2, 0)
        ramp = self.at(tree.nodes.new("ShaderNodeValToRGB"), 0, 0)
        ramp.color_ramp.elements[0].position = 0.499
        ramp.color_ramp.elements[1].position = 0.501
        tree.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])

        tree.links.new(selected[0].outputs["Shader"], group.inputs["Shader Lower"])
        tree.links.new(selected[1].outputs["Shader"], group.inputs["Shader Upper"])
        tree.links.new(ramp.outputs["Color"], group.inputs["Mask"])

        return{'FINISHED'}    

class DummyGroup:
    def __init__(self, tree):
        self.node_tree = tree        

class NW_GenerateDistortionOperator(Operator, NW_NodeUtils):
    bl_idname = "material.nw_generate_distortion_setup_op"
    bl_label = "UV Vector Distortion"
    bl_description = "Add UV Vector Distortion Group (Setup from https://cgmasters.net)."
    bl_options = {'REGISTER', 'UNDO'}        

    def execute(self, context):
        name = "NW Vector Distortion"

        # Check if already exists ..
        if bpy.data.node_groups.find(name) < 0:
            # No, create it.
            tree, input, output = self.create_group_tree(name, 4)
            group = DummyGroup(tree)

            noise = self.at(tree.nodes.new("ShaderNodeTexNoise"), 1, 0)
            sub = self.at(self.create_math_node(tree, "SUBTRACT"), 2, 0)
            mix = self.at(tree.nodes.new("ShaderNodeMixRGB"), 3, 0)
            mix.blend_type = "ADD"

            inVector = self.create_group_input(group, input, "Vector", "Vector")
            tree.links.new(inVector, noise.inputs["Vector"])
            tree.links.new(inVector, mix.inputs["Color1"])
            tree.links.new(noise.outputs["Fac"], sub.inputs[0])
            tree.links.new(sub.outputs["Value"], mix.inputs["Color2"])
            tree.links.new(mix.outputs["Color"], self.create_group_output(group, output, "Vector", "Vector"))

            tree.links.new(self.create_group_input(group, input, "Float", "Scale", 20.0), noise.inputs["Scale"])
            tree.links.new(self.create_group_input(group, input, "Float", "Detail", 2.0), noise.inputs["Detail"])
            tree.links.new(self.create_group_input(group, input, "Float", "Intensity", 0.0), mix.inputs["Fac"])

        # Instanciate group ..
        bpy.ops.node.add_node(
            type="ShaderNodeGroup", 
            use_transform=True, 
            settings=[{
                "name": "node_tree", 
                "value": "bpy.data.node_groups['%s']" % name
                }]
        )
        return bpy.ops.node.translate_attach_remove_on_cancel('INVOKE_DEFAULT')

class NW_GenerateBlurOperator(Operator, NW_NodeUtils):
    bl_idname = "material.nw_generate_blur_setup_op"
    bl_label = "UV Vector Blur"
    bl_description = "Add UV Vector Blur Group (Setup from https://cgmasters.net)."
    bl_options = {'REGISTER', 'UNDO'}        

    def execute(self, context):
        name = "NW Vector Blur"

        # Check if already exists ..
        if bpy.data.node_groups.find(name) < 0:
            # No, create it.
            tree, input, output = self.create_group_tree(name, 6)
            group = DummyGroup(tree)

            noiseScale = self.at(self.create_math_node(tree, "MULTIPLY", def1=10000.0), 1, -1)
            noise = self.at(tree.nodes.new("ShaderNodeTexNoise"), 2, 0)
            sub = self.at(self.create_math_node(tree, "SUBTRACT"), 3, 0)
            mixScale = self.at(self.create_math_node(tree, "DIVIDE", def1=1000.0), 4, -1)
            mix = self.at(tree.nodes.new("ShaderNodeMixRGB"), 5, 0)
            mix.blend_type = "ADD"

            inVector = self.create_group_input(group, input, "Vector", "Vector")
            tree.links.new(inVector, noise.inputs["Vector"])
            tree.links.new(inVector, mix.inputs["Color1"])
            tree.links.new(noise.outputs["Fac"], sub.inputs[0])
            tree.links.new(sub.outputs["Value"], mix.inputs["Color2"])
            tree.links.new(mix.outputs["Color"], self.create_group_output(group, output, "Vector", "Vector"))

            tree.links.new(self.create_group_input(group, input, "Float", "Scale", 10.0), noiseScale.inputs[0])
            tree.links.new(noiseScale.outputs["Value"], noise.inputs["Scale"])
            tree.links.new(self.create_group_input(group, input, "Float", "Detail", 2.0), noise.inputs["Detail"])
            tree.links.new(self.create_group_input(group, input, "Float", "Intensity", 0.0), mixScale.inputs[0])
            tree.links.new(mixScale.outputs["Value"], mix.inputs["Fac"])

        # Instanciate group ..
        bpy.ops.node.add_node(
            type="ShaderNodeGroup", 
            use_transform=True, 
            settings=[{
                "name": "node_tree", 
                "value": "bpy.data.node_groups['%s']" % name
                }]
        )
        return bpy.ops.node.translate_attach_remove_on_cancel('INVOKE_DEFAULT')        
