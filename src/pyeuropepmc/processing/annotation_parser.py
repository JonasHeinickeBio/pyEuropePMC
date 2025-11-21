"""
Annotation Parser for Europe PMC Annotations API responses.

This module provides parsers for JSON-LD annotation data following the
W3C Open Annotation Data Model, with specific support for entity annotations,
sentence annotations, and relationship annotations.
"""

import logging
from typing import Any

__all__ = [
    "AnnotationParser",
    "parse_annotations",
    "extract_entities",
    "extract_sentences",
    "extract_relationships",
]

logger = logging.getLogger(__name__)


class AnnotationParser:
    """
    Parser for JSON-LD annotation responses from Europe PMC Annotations API.

    This parser handles the W3C Open Annotation Data Model format and provides
    methods to extract specific types of annotations.
    """

    @staticmethod
    def parse_annotations(response: dict[str, Any]) -> dict[str, Any]:
        """
        Parse a complete annotation response.

        Args:
            response: Raw JSON-LD response from the Annotations API

        Returns:
            Parsed annotation data with structured entities, sentences, and relationships

        Examples:
            >>> parser = AnnotationParser()
            >>> parsed = parser.parse_annotations(raw_response)
            >>> print(f"Found {len(parsed['entities'])} entities")
        """
        if not isinstance(response, dict):
            logger.warning("Invalid annotation response: expected dict")
            return {"entities": [], "sentences": [], "relationships": [], "raw": response}

        # Handle both single annotation and annotation lists
        annotations = response.get("annotations", [])
        if not isinstance(annotations, list):
            annotations = [annotations] if annotations else []

        # Extract different types of annotations
        entities = AnnotationParser.extract_entities(annotations)
        sentences = AnnotationParser.extract_sentences(annotations)
        relationships = AnnotationParser.extract_relationships(annotations)

        return {
            "entities": entities,
            "sentences": sentences,
            "relationships": relationships,
            "metadata": AnnotationParser._extract_metadata(response),
            "raw": response,
        }

    @staticmethod
    def extract_entities(annotations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Extract entity annotations from a list of annotations.

        Entity annotations include mentions of genes, diseases, chemicals,
        organisms, and other biological entities.

        Args:
            annotations: List of annotation objects

        Returns:
            List of entity annotation dictionaries

        Examples:
            >>> entities = AnnotationParser.extract_entities(annotations)
            >>> for entity in entities:
            ...     print(f"{entity['type']}: {entity['exact']}")
        """
        entities = []

        for annotation in annotations:
            if not isinstance(annotation, dict):
                continue

            # Entity annotations typically have tags with entity IDs
            tags = annotation.get("tags", [])
            if not tags:
                continue

            # Extract entity information
            for tag in tags:
                if not isinstance(tag, dict):
                    continue

                entity = {
                    "id": tag.get("uri") or tag.get("@id", ""),
                    "name": tag.get("name", ""),
                    "type": AnnotationParser._extract_entity_type(tag),
                    "exact": annotation.get("exact", ""),
                    "prefix": annotation.get("prefix", ""),
                    "postfix": annotation.get("postfix", ""),
                    "section": annotation.get("section", ""),
                    "provider": AnnotationParser._extract_provider(annotation),
                    "confidence": tag.get("confidence"),
                }

                # Add position information if available
                position = annotation.get("position")
                if position:
                    entity["position"] = position

                entities.append(entity)

        return entities

    @staticmethod
    def extract_sentences(annotations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Extract sentence annotations from a list of annotations.

        Sentence annotations provide context for entity mentions and relationships.

        Args:
            annotations: List of annotation objects

        Returns:
            List of sentence annotation dictionaries

        Examples:
            >>> sentences = AnnotationParser.extract_sentences(annotations)
            >>> for sentence in sentences:
            ...     print(sentence['text'])
        """
        sentences = []

        for annotation in annotations:
            if not isinstance(annotation, dict):
                continue

            # Sentence annotations typically have a target with text
            target = annotation.get("target")
            if not target:
                continue

            # Check if this annotation represents a sentence
            annotation_type = annotation.get("type") or annotation.get("@type", "")
            if "sentence" in str(annotation_type).lower():
                sentence = {
                    "text": annotation.get("exact", ""),
                    "section": annotation.get("section", ""),
                    "source": annotation.get("source", ""),
                    "provider": AnnotationParser._extract_provider(annotation),
                }

                # Add position information if available
                position = annotation.get("position")
                if position:
                    sentence["position"] = position

                sentences.append(sentence)

        return sentences

    @staticmethod
    def extract_relationships(annotations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Extract relationship annotations from a list of annotations.

        Relationship annotations describe interactions, associations, or other
        relationships between biological entities (e.g., gene-disease associations).

        Args:
            annotations: List of annotation objects

        Returns:
            List of relationship annotation dictionaries

        Examples:
            >>> relationships = AnnotationParser.extract_relationships(annotations)
            >>> for rel in relationships:
            ...     print(f"{rel['subject']} {rel['predicate']} {rel['object']}")
        """
        relationships = []

        for annotation in annotations:
            if not isinstance(annotation, dict):
                continue

            # Relationship annotations have multiple tags representing entities
            tags = annotation.get("tags", [])
            if len(tags) < 2:
                continue

            # Check if this is a relationship annotation
            annotation_type = annotation.get("type") or annotation.get("@type", "")
            relation_type = annotation.get("relation") or annotation.get("predicate")

            if relation_type or "relationship" in str(annotation_type).lower():
                # Extract subject and object entities
                subject = tags[0] if len(tags) > 0 else {}
                obj = tags[1] if len(tags) > 1 else {}

                relationship = {
                    "subject": {
                        "id": subject.get("uri") or subject.get("@id", ""),
                        "name": subject.get("name", ""),
                        "type": AnnotationParser._extract_entity_type(subject),
                    },
                    "predicate": relation_type or "related_to",
                    "object": {
                        "id": obj.get("uri") or obj.get("@id", ""),
                        "name": obj.get("name", ""),
                        "type": AnnotationParser._extract_entity_type(obj),
                    },
                    "sentence": annotation.get("exact", ""),
                    "section": annotation.get("section", ""),
                    "provider": AnnotationParser._extract_provider(annotation),
                }

                relationships.append(relationship)

        return relationships

    @staticmethod
    def _extract_entity_type(tag: dict[str, Any]) -> str:
        """Extract entity type from a tag."""
        # Check various possible fields for entity type
        entity_type = tag.get("type") or tag.get("@type", "")

        # Extract from URI if not in type field
        if not entity_type:
            uri = tag.get("uri") or tag.get("@id", "")
            if uri and ":" in uri:
                entity_type = uri.split(":")[0]

        return str(entity_type)

    @staticmethod
    def _extract_provider(annotation: dict[str, Any]) -> str:
        """Extract provider information from an annotation."""
        # Check various possible fields for provider
        provider = annotation.get("provider", {})
        if isinstance(provider, dict):
            return provider.get("name", "Unknown")
        elif isinstance(provider, str):
            return provider

        # Check annotator field as fallback
        annotator = annotation.get("annotator", {})
        if isinstance(annotator, dict):
            return annotator.get("name", "Unknown")
        elif isinstance(annotator, str):
            return annotator

        return "Unknown"

    @staticmethod
    def _extract_metadata(response: dict[str, Any]) -> dict[str, Any]:
        """Extract metadata from annotation response."""
        return {
            "total_count": response.get("totalCount", 0),
            "page": response.get("page", 1),
            "page_size": response.get("pageSize", 25),
            "version": response.get("version", ""),
            "source": response.get("source", ""),
        }


# Convenience functions for direct use
def parse_annotations(response: dict[str, Any]) -> dict[str, Any]:
    """
    Parse annotation response (convenience function).

    Args:
        response: Raw JSON-LD response from the Annotations API

    Returns:
        Parsed annotation data

    Examples:
        >>> parsed = parse_annotations(raw_response)
        >>> print(f"Found {len(parsed['entities'])} entities")
    """
    return AnnotationParser.parse_annotations(response)


def extract_entities(annotations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Extract entities from annotations (convenience function).

    Args:
        annotations: List of annotation objects

    Returns:
        List of entity dictionaries
    """
    return AnnotationParser.extract_entities(annotations)


def extract_sentences(annotations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Extract sentences from annotations (convenience function).

    Args:
        annotations: List of annotation objects

    Returns:
        List of sentence dictionaries
    """
    return AnnotationParser.extract_sentences(annotations)


def extract_relationships(annotations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Extract relationships from annotations (convenience function).

    Args:
        annotations: List of annotation objects

    Returns:
        List of relationship dictionaries
    """
    return AnnotationParser.extract_relationships(annotations)
