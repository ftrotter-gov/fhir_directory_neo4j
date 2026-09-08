"""Bounded extraction of FHIR resources from standard FHIR container shapes."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class FHIRResourceRecord:
    """One extracted FHIR resource plus its container context."""

    resource: Dict[str, Any]
    resource_type: str
    source_path: str
    container_type: Optional[str] = None
    bundle_type: Optional[str] = None
    search_mode: Optional[str] = None
    is_contained: bool = False


@dataclass(frozen=True)
class FHIRDiagnostic:
    """A parsing, pagination, or OperationOutcome diagnostic."""

    severity: str
    code: str
    message: str
    source_path: str


@dataclass
class FHIRParseResult:
    """Resources and diagnostics extracted from one payload."""

    resources: List[FHIRResourceRecord] = field(default_factory=list)
    diagnostics: List[FHIRDiagnostic] = field(default_factory=list)


class FHIRParser:
    """Extract resources only through recognized standard FHIR container fields."""

    DEFAULT_MAX_DEPTH = 3

    @staticmethod
    def extract_resources(
        *, payload: Any, max_depth: int = DEFAULT_MAX_DEPTH
    ) -> FHIRParseResult:
        """Extract direct, Bundle, Parameters, and contained FHIR resources."""
        result = FHIRParseResult()
        FHIRParser._walk_resource(
            payload=payload,
            source_path="$",
            depth=0,
            max_depth=max_depth,
            result=result,
        )
        return result

    @staticmethod
    def _walk_resource(
        *,
        payload: Any,
        source_path: str,
        depth: int,
        max_depth: int,
        result: FHIRParseResult,
        container_type: Optional[str] = None,
        bundle_type: Optional[str] = None,
        search_mode: Optional[str] = None,
        is_contained: bool = False,
    ) -> None:
        """Walk one FHIR resource and recognized child-resource fields."""
        if not isinstance(payload, dict):
            return
        resource_type = payload.get("resourceType")
        if not isinstance(resource_type, str) or not resource_type:
            return

        if resource_type == "OperationOutcome":
            FHIRParser._record_operation_outcome(
                outcome=payload, source_path=source_path, result=result
            )
        elif resource_type == "Bundle":
            FHIRParser._record_bundle_diagnostics(
                bundle=payload, source_path=source_path, result=result
            )
            if depth >= max_depth:
                FHIRParser._record_depth_limit(
                    source_path=source_path, result=result
                )
                return
            current_bundle_type = payload.get("type")
            for entry_index, entry in enumerate(payload.get("entry", [])):
                if not isinstance(entry, dict):
                    continue
                entry_resource = entry.get("resource")
                entry_search = entry.get("search", {})
                entry_search_mode = (
                    entry_search.get("mode") if isinstance(entry_search, dict) else None
                )
                FHIRParser._walk_resource(
                    payload=entry_resource,
                    source_path=f"{source_path}.entry[{entry_index}].resource",
                    depth=depth + 1,
                    max_depth=max_depth,
                    result=result,
                    container_type="Bundle",
                    bundle_type=current_bundle_type,
                    search_mode=entry_search_mode,
                )
            return
        elif resource_type == "Parameters":
            if depth >= max_depth:
                FHIRParser._record_depth_limit(
                    source_path=source_path, result=result
                )
                return
            FHIRParser._walk_parameters(
                parameters=payload.get("parameter", []),
                source_path=f"{source_path}.parameter",
                depth=depth + 1,
                max_depth=max_depth,
                result=result,
            )
            return
        else:
            result.resources.append(
                FHIRResourceRecord(
                    resource=payload,
                    resource_type=resource_type,
                    source_path=source_path,
                    container_type=container_type,
                    bundle_type=bundle_type,
                    search_mode=search_mode,
                    is_contained=is_contained,
                )
            )

        contained_resources = payload.get("contained", [])
        if contained_resources and depth >= max_depth:
            FHIRParser._record_depth_limit(source_path=source_path, result=result)
            return
        if isinstance(contained_resources, list):
            for contained_index, contained_resource in enumerate(contained_resources):
                FHIRParser._walk_resource(
                    payload=contained_resource,
                    source_path=f"{source_path}.contained[{contained_index}]",
                    depth=depth + 1,
                    max_depth=max_depth,
                    result=result,
                    container_type=resource_type,
                    is_contained=True,
                )

    @staticmethod
    def _walk_parameters(
        *,
        parameters: Any,
        source_path: str,
        depth: int,
        max_depth: int,
        result: FHIRParseResult,
    ) -> None:
        """Walk Parameters.parameter and recursively nested part elements."""
        if not isinstance(parameters, list):
            return
        for parameter_index, parameter in enumerate(parameters):
            if not isinstance(parameter, dict):
                continue
            parameter_path = f"{source_path}[{parameter_index}]"
            FHIRParser._walk_resource(
                payload=parameter.get("resource"),
                source_path=f"{parameter_path}.resource",
                depth=depth,
                max_depth=max_depth,
                result=result,
                container_type="Parameters",
            )
            parts = parameter.get("part")
            if parts:
                if depth >= max_depth:
                    FHIRParser._record_depth_limit(
                        source_path=parameter_path, result=result
                    )
                else:
                    FHIRParser._walk_parameters(
                        parameters=parts,
                        source_path=f"{parameter_path}.part",
                        depth=depth + 1,
                        max_depth=max_depth,
                        result=result,
                    )

    @staticmethod
    def _record_operation_outcome(
        *, outcome: Dict[str, Any], source_path: str, result: FHIRParseResult
    ) -> None:
        """Convert OperationOutcome issues to structured parser diagnostics."""
        issues = outcome.get("issue", [])
        if not isinstance(issues, list) or not issues:
            result.diagnostics.append(
                FHIRDiagnostic(
                    severity="warning",
                    code="operation-outcome",
                    message="OperationOutcome did not include any issues.",
                    source_path=source_path,
                )
            )
            return
        for issue in issues:
            if not isinstance(issue, dict):
                continue
            details = issue.get("details", {})
            details_text = details.get("text") if isinstance(details, dict) else None
            message = issue.get("diagnostics") or details_text or "No diagnostic message"
            result.diagnostics.append(
                FHIRDiagnostic(
                    severity=str(issue.get("severity") or "information"),
                    code=str(issue.get("code") or "operation-outcome"),
                    message=str(message),
                    source_path=source_path,
                )
            )

    @staticmethod
    def _record_bundle_diagnostics(
        *, bundle: Dict[str, Any], source_path: str, result: FHIRParseResult
    ) -> None:
        """Report pagination metadata that affects cache completeness."""
        links = bundle.get("link", [])
        if not isinstance(links, list):
            return
        for link in links:
            if isinstance(link, dict) and link.get("relation") == "next":
                total = bundle.get("total")
                total_text = f" Bundle total is {total}." if total is not None else ""
                result.diagnostics.append(
                    FHIRDiagnostic(
                        severity="warning",
                        code="pagination",
                        message=(
                            "Bundle has a next link and this file may contain only one "
                            f"page of results.{total_text}"
                        ),
                        source_path=source_path,
                    )
                )
                return

    @staticmethod
    def _record_depth_limit(*, source_path: str, result: FHIRParseResult) -> None:
        """Report a bounded-recursion stop."""
        result.diagnostics.append(
            FHIRDiagnostic(
                severity="warning",
                code="maximum-depth",
                message="FHIR container recursion stopped at the configured maximum depth.",
                source_path=source_path,
            )
        )