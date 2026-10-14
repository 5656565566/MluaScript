from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
import pytest
from lupa.lua54 import LuaRuntime
from maa.controller import CustomController


class CoordinateController(CustomController):
    def __init__(self, width: int, height: int):
        self.image = np.zeros((height, width, 3), dtype=np.uint8)
        self.clicks: list[tuple[int, int]] = []
        super().__init__()

    def connect(self) -> bool:
        return True

    def request_uuid(self) -> str:
        return "coordinate-test"

    def get_features(self) -> int:
        return 0

    def screencap(self):
        return self.image

    def click(self, x: int, y: int) -> bool:
        self.clicks.append((x, y))
        return True


@pytest.fixture(scope="module")
def coordinate_expression() -> str:
    web_root = Path(__file__).resolve().parents[3] / "src" / "mluascript_web"
    result = subprocess.run(
        ["node", "--input-type=module", "-e", '''
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import * as Blockly from 'blockly';
import { luaGenerator } from 'blockly/lua';
const constants = pathToFileURL(process.cwd() + '/src/blockly/constants.js').href;
const source = readFileSync('src/blockly/blocks/device.js', 'utf8').replace("'../constants'", JSON.stringify(constants));
const { deviceBlocks } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const spec = deviceBlocks.find(block => block.type === 'maa_calc_coordinate');
Blockly.defineBlocksWithJsonArray([{ type: spec.type, ...spec.definition }]);
luaGenerator.forBlock[spec.type] = spec.generator;
Blockly.Blocks.coordinate_value = { init() { this.setOutput(true, 'Number'); } };
luaGenerator.forBlock.coordinate_value = block => [block.variable, luaGenerator.ORDER_ATOMIC];
const workspace = new Blockly.Workspace();
const block = workspace.newBlock(spec.type);
for (const [input, variable] of [['REAL_COORD', 'coord'], ['REAL_SIZE', 'size']]) {
    const child = workspace.newBlock('coordinate_value');
    child.variable = variable;
    block.getInput(input).connection.connect(child.outputConnection);
}
luaGenerator.init(workspace);
console.log(JSON.stringify(luaGenerator.blockToCode(block)[0]));
luaGenerator.finish('');
workspace.dispose();
'''],
        cwd=web_root,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("width,height", [(2400, 1080), (1080, 2400), (1920, 1080), (1080, 1920), (1024, 768), (1001, 2000)])
def test_blockly_coordinate_matches_native_screenshot_and_click(coordinate_expression, width, height) -> None:
    controller = CoordinateController(width, height)
    assert controller.post_connection().wait().succeeded
    assert controller.post_screencap().wait().succeeded
    image = controller.cached_image
    lua = LuaRuntime()
    lua.globals().maa = lua.table_from({"get_resolution": lambda: lua.table_from({"width": width, "height": height})})
    # Values are chosen in the screenshot, then mapped to the raw device before conversion.
    x, y = int(image.shape[1] / 2), int(image.shape[0] / 2)
    lua.globals().coord, lua.globals().size = x * width / image.shape[1], width
    assert lua.eval(coordinate_expression) == pytest.approx(x)
    lua.globals().coord, lua.globals().size = y * height / image.shape[0], height
    assert lua.eval(coordinate_expression) == pytest.approx(y)
    assert controller.post_click(x, y).wait().succeeded
    assert controller.clicks == [(int(x * width / image.shape[1] + 0.5), int(y * height / image.shape[0] + 0.5))]
