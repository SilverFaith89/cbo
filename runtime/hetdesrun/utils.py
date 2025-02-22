"""Utilities for scripting and in particular component/workflow deployment"""

import datetime
import json
import logging
import random
from enum import Enum
from typing import Any
from uuid import UUID

import requests  # noqa: F401
from plotly.graph_objects import Figure
from plotly.utils import PlotlyJSONEncoder
from pydantic import BaseModel

from hetdesrun.datatypes import DataType
from hetdesrun.webservice.config import get_config

logger = logging.getLogger(__name__)


def check_aware(dt: datetime.datetime) -> bool:
    """check whether datetime is non-naive"""
    # see https://stackoverflow.com/a/27596917
    return dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None


def check_explicit_utc(dt: datetime.datetime) -> bool:
    """check whether datetime is explicitely utc"""
    return check_aware(dt) and dt.utcoffset().total_seconds() == 0  # type: ignore


def get_backend_basic_auth() -> tuple[str | None, str | None] | None:
    if get_config().hd_backend_use_basic_auth:
        return (
            get_config().hd_backend_basic_auth_user,
            get_config().hd_backend_basic_auth_password,
        )
    return None


def get_uuid_from_seed(seed_str: str) -> UUID:
    """Generate UUID from string

    The seed_str is used to reset the random number generation seed so that this
    function always returns same UUID for the same seed_str.

    This may be used to get reproducible UUIDs from human-readable strings in scripts
    and tests. Should not be used anywhere else for security reasons.
    """
    random.seed(seed_str)
    return UUID(int=random.getrandbits(128))


def load_data(
    json_file: str, md_file: str, code_file: str | None = None
) -> tuple[dict | None, str | None, str | None]:
    """Loads structured and unstructured component / workflow data from files

    Helper function to load a bunch of data from
    * 3 files for a component (a json file, the documentation markdown file, the code file)
    * or from 2 files for a workflow (a json file, the documentation markdown file,).

    Args:
        json_file (str): path to the json file
        md_file (str): path to the documentation markdown file
        code_file (Optional[str], optional): Path to code file. Defaults to None. If None
            this function will only load the json file and the doc file.

    Returns:
        Union[Tuple[Any, str], Tuple[Any, str, str]]: A tuple with structured data
        from json file as first entry, documentation as second entry and if code_file
        is not None the code as third entry. If some part of loading failes, None is returned
    """
    with open(json_file, encoding="utf8") as f:
        try:
            info = json.load(f)
        except json.JSONDecodeError:
            logger.error("Could not decode %s", json_file)
            info = None
    doc: str | None
    try:
        with open(md_file, encoding="utf8") as f:
            doc = f.read()
    except FileNotFoundError:
        logger.error("Could not find documentation markdonw file %s", md_file)
        doc = None

    if code_file is None:
        return info, doc, None

    code: str | None
    try:
        with open(code_file, encoding="utf8") as f:
            code = f.read()
    except FileNotFoundError:
        logger.error("Could not find code file %s", code_file)
        code = None

    return info, doc, code


class State(str, Enum):
    """Representing state of component/workflow"""

    DRAFT = "DRAFT"
    RELEASED = "RELEASED"
    DISABLED = "DISABLED"


class Type(str, Enum):
    COMPONENT = "COMPONENT"
    WORKFLOW = "WORKFLOW"


class IODTO(BaseModel):
    id: UUID  # noqa: A003
    name: str
    posX: int = 0
    posY: int = 0
    type: DataType  # noqa: A003


class ComponentDTO(BaseModel):
    """Component DTO as expected by Backend Service"""

    name: str
    category: str
    code: str
    description: str
    groupId: UUID
    id: UUID  # noqa: A003
    inputs: list[IODTO]
    outputs: list[IODTO]
    state: State = State.RELEASED
    tag: str
    testInput: dict = {}
    type: Type = Type.COMPONENT  # noqa: A003


def model_to_pretty_json_str(pydantic_model: BaseModel) -> str:
    """Pretty printing Pydantic Models

    For logging etc.
    """
    return json.dumps(json.loads(pydantic_model.json()), indent=2, sort_keys=True)


def plotly_fig_to_json_dict(fig: Figure) -> Any:
    """Turn Plotly figure into a Python dict-like object

    This function can be used in visualization components to obtain the
    correct plotly json-like object from a Plotly Figure object.

    See visualization components from the accompanying base components for
    examples on usage.
    """
    # possibly quite inefficient (multiple serialisation / deserialization) but
    # guarantees that the PlotlyJSONEncoder is used and so the resulting Json
    # should be definitely compatible with the plotly javascript library:
    return json.loads(json.dumps(fig.to_plotly_json(), cls=PlotlyJSONEncoder))
