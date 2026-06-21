"""Workflow configuration validator.

Validates workflow configurations before execution to catch errors early.

Usage:
    from app.services.workflow.validator import validate_workflow_config

    errors = validate_workflow_config(config_json)
    if errors:
        raise ValueError(f"Invalid workflow config: {errors}")
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Maximum limits for workflow configuration
MAX_NODES = 100
MAX_EDGES = 200
MAX_DOCUMENT_IDS = 1000
MAX_PROMPT_LENGTH = 5000
MAX_LABEL_LENGTH = 200


def validate_workflow_config(config_json: dict) -> list[str]:
    """Validate a workflow configuration.

    Args:
        config_json: Workflow configuration with nodes and edges

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    # Check required fields
    if not isinstance(config_json, dict):
        return ["配置必须是字典类型"]

    nodes = config_json.get("nodes", [])
    edges = config_json.get("edges", [])

    # Validate nodes
    if not isinstance(nodes, list):
        errors.append("nodes必须是列表类型")
        return errors

    if len(nodes) > MAX_NODES:
        errors.append(f"节点数量超过限制 ({len(nodes)} > {MAX_NODES})")

    if len(nodes) == 0:
        errors.append("工作流必须至少有一个节点")
        return errors

    # Validate each node
    node_ids = set()
    for i, node in enumerate(nodes):
        node_errors = _validate_node(node, i)
        errors.extend(node_errors)

        # Check for duplicate node IDs
        node_id = node.get("id")
        if node_id in node_ids:
            errors.append(f"节点ID重复: {node_id}")
        node_ids.add(node_id)

    # Validate edges
    if not isinstance(edges, list):
        errors.append("edges必须是列表类型")
        return errors

    if len(edges) > MAX_EDGES:
        errors.append(f"边数量超过限制 ({len(edges)} > {MAX_EDGES})")

    # Validate each edge
    for i, edge in enumerate(edges):
        edge_errors = _validate_edge(edge, i, node_ids)
        errors.extend(edge_errors)

    # Check for source node
    has_source = any(node.get("type") == "source" for node in nodes)
    if not has_source:
        errors.append("工作流必须有一个source类型的节点")

    # Validate specific node configurations
    for node in nodes:
        config_errors = _validate_node_config(node)
        errors.extend(config_errors)

    return errors


def _validate_node(node: dict, index: int) -> list[str]:
    """Validate a single node.

    Args:
        node: Node configuration
        index: Node index in the list

    Returns:
        List of error messages
    """
    errors = []
    prefix = f"节点[{index}]"

    if not isinstance(node, dict):
        errors.append(f"{prefix} 必须是字典类型")
        return errors

    # Check required fields
    if "id" not in node:
        errors.append(f"{prefix} 缺少'id'字段")
    elif not isinstance(node["id"], str) or not node["id"].strip():
        errors.append(f"{prefix} 'id'必须是非空字符串")

    if "type" not in node:
        errors.append(f"{prefix} 缺少'type'字段")
    elif not isinstance(node["type"], str) or not node["type"].strip():
        errors.append(f"{prefix} 'type'必须是非空字符串")

    # Check optional fields
    if "label" in node:
        if not isinstance(node["label"], str):
            errors.append(f"{prefix} 'label'必须是字符串")
        elif len(node["label"]) > MAX_LABEL_LENGTH:
            errors.append(f"{prefix} 'label'长度超过限制 ({len(node['label'])} > {MAX_LABEL_LENGTH})")

    if "config" in node and not isinstance(node["config"], dict):
        errors.append(f"{prefix} 'config'必须是字典类型")

    return errors


def _validate_edge(edge: dict, index: int, node_ids: set) -> list[str]:
    """Validate a single edge.

    Args:
        edge: Edge configuration
        index: Edge index in the list
        node_ids: Set of valid node IDs

    Returns:
        List of error messages
    """
    errors = []
    prefix = f"边[{index}]"

    if not isinstance(edge, dict):
        errors.append(f"{prefix} 必须是字典类型")
        return errors

    # Check required fields
    if "source" not in edge:
        errors.append(f"{prefix} 缺少'source'字段")
    elif edge["source"] not in node_ids:
        errors.append(f"{prefix} 'source'引用的节点不存在: {edge['source']}")

    if "target" not in edge:
        errors.append(f"{prefix} 缺少'target'字段")
    elif edge["target"] not in node_ids:
        errors.append(f"{prefix} 'target'引用的节点不存在: {edge['target']}")

    # Check for self-loops
    if edge.get("source") == edge.get("target"):
        errors.append(f"{prefix} 不能有自环")

    return errors


def _validate_node_config(node: dict) -> list[str]:
    """Validate node-specific configuration.

    Args:
        node: Node configuration

    Returns:
        List of error messages
    """
    errors = []
    node_type = node.get("type", "")
    config = node.get("config", {})
    node_id = node.get("id", "unknown")

    if not isinstance(config, dict):
        return errors

    # Validate source node
    if node_type == "source":
        filt = config.get("filter", "all")
        if filt not in ("all", "folder", "tag", "status", "ids"):
            errors.append(f"节点'{node_id}' 无效的filter类型: {filt}")

        if filt == "ids":
            doc_ids = config.get("document_ids", [])
            if not isinstance(doc_ids, list):
                errors.append(f"节点'{node_id}' 'document_ids'必须是列表")
            elif len(doc_ids) > MAX_DOCUMENT_IDS:
                errors.append(f"节点'{node_id}' 'document_ids'数量超过限制 ({len(doc_ids)} > {MAX_DOCUMENT_IDS})")
            elif any(not isinstance(id_, int) or id_ <= 0 for id_ in doc_ids):
                errors.append(f"节点'{node_id}' 'document_ids'必须是正整数列表")

    # Validate condition node
    elif node_type == "condition":
        if "field" not in config:
            errors.append(f"节点'{node_id}' 条件节点缺少'field'配置")
        if "operator" not in config:
            errors.append(f"节点'{node_id}' 条件节点缺少'operator'配置")
        elif config["operator"] not in ("eq", "neq", "gte", "lte", "gt", "lt", "contains", "not_contains", "is_empty", "is_not_empty"):
            errors.append(f"节点'{node_id}' 无效的操作符: {config['operator']}")
        if "true_branch" not in config:
            errors.append(f"节点'{node_id}' 条件节点缺少'true_branch'配置")
        if "false_branch" not in config:
            errors.append(f"节点'{node_id}' 条件节点缺少'false_branch'配置")

    # Validate loop node
    elif node_type == "loop":
        if "source_field" not in config:
            errors.append(f"节点'{node_id}' 循环节点缺少'source_field'配置")
        if "body_nodes" not in config:
            errors.append(f"节点'{node_id}' 循环节点缺少'body_nodes'配置")
        elif not isinstance(config["body_nodes"], list):
            errors.append(f"节点'{node_id}' 'body_nodes'必须是列表")

        max_iterations = config.get("max_iterations", 50)
        if not isinstance(max_iterations, int) or max_iterations <= 0:
            errors.append(f"节点'{node_id}' 'max_iterations'必须是正整数")
        elif max_iterations > 1000:
            errors.append(f"节点'{node_id}' 'max_iterations'过大 ({max_iterations} > 1000)")

    # Validate custom_prompt node
    elif node_type == "custom_prompt":
        prompt = config.get("prompt", "")
        if not prompt:
            errors.append(f"节点'{node_id}' 自定义提示节点缺少'prompt'配置")
        elif len(prompt) > MAX_PROMPT_LENGTH:
            errors.append(f"节点'{node_id}' 'prompt'长度超过限制 ({len(prompt)} > {MAX_PROMPT_LENGTH})")

    # Validate format_convert node
    elif node_type == "format_convert":
        output_format = config.get("output_format", "")
        if output_format not in ("latex", "html", "docx", "markdown"):
            errors.append(f"节点'{node_id}' 无效的输出格式: {output_format}")

    # Validate export node
    elif node_type == "export":
        output_format = config.get("format", "")
        if output_format not in ("latex", "html", "docx", "markdown", "pdf"):
            errors.append(f"节点'{node_id}' 无效的导出格式: {output_format}")

    # Validate ai_analyze node
    elif node_type == "ai_analyze":
        analysis_type = config.get("analysis_type", "")
        if analysis_type not in ("toc_extraction", "structure_analysis", "quality_assessment", "academic_structure"):
            errors.append(f"节点'{node_id}' 无效的分析类型: {analysis_type}")

    # Validate approval node
    elif node_type == "approval":
        timeout_hours = config.get("timeout_hours", 72)
        if not isinstance(timeout_hours, (int, float)) or timeout_hours <= 0:
            errors.append(f"节点'{node_id}' 'timeout_hours'必须是正数")

    return errors
