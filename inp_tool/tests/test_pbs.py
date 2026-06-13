"""pbs 模块单测 - Task 2: dataclass + from_dict + Task 3: detect + Task 4: render_pbs_name"""
import pytest
from inp_tool.pbs import PbsConfig, PbsIssue


class TestPbsConfig:
    def test_defaults(self):
        c = PbsConfig()
        assert c.enabled is True
        assert c.template is None
        assert c.naming == ""
        assert c.naming_ext == ""
        assert c.detect_basename is True
        assert c.basename_max_len == 8

    def test_from_dict_full(self):
        d = {
            "enabled": False,
            "template": "/path/to/source.pbs",
            "naming": "Mars-{alpha}",
            "naming_ext": ".pbs",
            "detect_basename": False,
            "basename_max_len": 12,
        }
        c = PbsConfig.from_dict(d)
        assert c.enabled is False
        assert c.template == "/path/to/source.pbs"
        assert c.naming == "Mars-{alpha}"
        assert c.naming_ext == ".pbs"
        assert c.detect_basename is False
        assert c.basename_max_len == 12

    def test_from_dict_empty(self):
        c = PbsConfig.from_dict({})
        assert c.enabled is True  # 默认
        assert c.template is None
        assert c.naming == ""

    def test_from_dict_partial(self):
        c = PbsConfig.from_dict({"naming": "Case-{alpha}"})
        assert c.naming == "Case-{alpha}"
        assert c.enabled is True  # 其他走默认


class TestPbsIssue:
    def test_construction(self):
        issue = PbsIssue(
            code="MISSING_MCFD_INP",
            severity="error",
            path="/path/to/source",
            message="找不到 mcfd.inp",
        )
        assert issue.code == "MISSING_MCFD_INP"
        assert issue.severity == "error"
        assert issue.path == "/path/to/source"
        assert issue.message == "找不到 mcfd.inp"


class TestDetectPbsTemplate:
    def test_finds_run_pbs(self, tmp_path):
        (tmp_path / "mcfd.inp").write_text("placeholder")
        (tmp_path / "run_cfdpp.pbs").write_text("#!/bin/bash\n#PBS -N test\n")
        from inp_tool.pbs import detect_pbs_template
        result = detect_pbs_template(str(tmp_path))
        assert result == str(tmp_path / "run_cfdpp.pbs")

    def test_no_pbs_returns_none(self, tmp_path):
        (tmp_path / "mcfd.inp").write_text("placeholder")
        from inp_tool.pbs import detect_pbs_template
        assert detect_pbs_template(str(tmp_path)) is None

    def test_multiple_pbs_returns_first_with_warning(self, tmp_path, capsys):
        (tmp_path / "run_a.pbs").write_text("#PBS -N a")
        (tmp_path / "run_b.pbs").write_text("#PBS -N b")
        from inp_tool.pbs import detect_pbs_template
        result = detect_pbs_template(str(tmp_path))
        # 字母序第一个 run_a.pbs
        assert result == str(tmp_path / "run_a.pbs")
        captured = capsys.readouterr()
        # warning 输出到 stderr(spec §6 + 计划 Task 3)
        assert "多个" in captured.err or "warning" in captured.err.lower()

    def test_explicit_template_overrides(self, tmp_path):
        (tmp_path / "run_a.pbs").write_text("#PBS -N a")
        explicit = tmp_path / "custom.pbs"
        explicit.write_text("#PBS -N custom")
        from inp_tool.pbs import detect_pbs_template
        result = detect_pbs_template(str(tmp_path), explicit_template=str(explicit))
        assert result == str(explicit)


class TestRenderPbsName:
    def test_default_shortname_basic(self):
        from inp_tool.pbs import render_pbs_name
        name = render_pbs_name(
            params={"alpha": 4, "beta": 0, "mach": 0.6},
            multi_value_axes=["alpha", "mach"],
            base_basename="Marspath",
            max_len=200,  # v0.14.0: 显式避开集群 15 字符约束,保留旧行为断言
        )
        assert name == "Marspath_a04_m0.60"

    def test_single_value_axis_excluded(self):
        from inp_tool.pbs import render_pbs_name
        name = render_pbs_name(
            params={"alpha": 4, "beta": 0, "mach": 0.6},
            multi_value_axes=["alpha"],  # beta 和 mach 是单值
            base_basename="Base",
        )
        assert name == "Base_a04"

    def test_empty_multi_value_axes(self):
        from inp_tool.pbs import render_pbs_name
        name = render_pbs_name(
            params={"alpha": 4, "mach": 0.6},
            multi_value_axes=[],
            base_basename="Case",
        )
        assert name == "Case"

    def test_axis_short_format_floats(self):
        from inp_tool.pbs import render_pbs_name
        # alpha=4.5 → a04.5(整数部分补零到 2 位)
        # mach=0.85 → m0.85(原样保留)
        name = render_pbs_name(
            params={"alpha": 4.5, "mach": 0.85},
            multi_value_axes=["alpha", "mach"],
            base_basename="B",
        )
        assert name == "B_a04.5_m0.85"

    def test_axis_short_int_truncates_decimal(self):
        from inp_tool.pbs import render_pbs_name
        # T_inf=288.15 → T288(整数优先,小数点后 2 位;纯整数去小数)
        name = render_pbs_name(
            params={"T_inf": 288.15},
            multi_value_axes=["T_inf"],
            base_basename="B",
        )
        assert name == "B_T288"

    def test_axis_short_negative(self):
        from inp_tool.pbs import render_pbs_name
        # 负值不补零,原样输出
        name = render_pbs_name(
            params={"alpha": -2.0},
            multi_value_axes=["alpha"],
            base_basename="B",
        )
        assert name == "B_a-2.0"


class TestRenderPbsNameUserTemplate:
    def test_user_template_overrides_default(self):
        from inp_tool.pbs import render_pbs_name
        name = render_pbs_name(
            params={"alpha": 4, "mach": 0.6},
            multi_value_axes=["alpha", "mach"],
            base_basename="Marspath",
            user_template="Mars-{alpha}-{mach}",
        )
        assert name == "Mars-4-0.6"

    def test_user_template_with_unknown_placeholder_raises(self):
        from inp_tool.pbs import render_pbs_name
        with pytest.raises(KeyError):
            render_pbs_name(
                params={"alpha": 4},
                multi_value_axes=["alpha"],
                base_basename="B",
                user_template="Case-{nonexistent}",
            )


class TestRenderPbsNameTruncation:
    def test_truncates_over_max_len(self):
        from inp_tool.pbs import render_pbs_name
        # 显式传 max_len=15(plan Task 5)
        name = render_pbs_name(
            params={"alpha": 4, "beta": 0, "mach": 0.6},
            multi_value_axes=["alpha", "beta", "mach"],
            base_basename="VeryLongBaseName",  # 16 字符
            max_len=15,
        )
        assert len(name) <= 15
        assert name.endswith(".")

    def test_custom_max_len(self):
        from inp_tool.pbs import render_pbs_name
        # "Base_a04" = 8 字符, max_len=7 时会截断到 "Base_a." (7 字符)
        name = render_pbs_name(
            params={"alpha": 4},
            multi_value_axes=["alpha"],
            base_basename="Base",
            max_len=7,
        )
        assert name == "Base_a."


class TestRenderPbsNameSanitization:
    def test_sanitize_special_chars(self):
        from inp_tool.pbs import render_pbs_name
        # 注入特殊字符:用 user_template 直接传
        name = render_pbs_name(
            params={"x": 1},
            multi_value_axes=["x"],
            base_basename="Base",
            user_template="Hello World!",
        )
        # 空格和 ! 都不是合法 PBS 字符,被替换
        assert " " not in name
        assert "!" not in name
        assert name == "Hello_World_"


class TestValidateBaseCaseFiles:
    def _make_minimal_source(self, tmp_path):
        """构造一个最小可用的 source_dir(含 mcfd.inp + tsteps + physics blocks + grid 文件)"""
        mcfd = tmp_path / "mcfd.inp"
        mcfd.write_text(
            "tsteps begin\n  ntstep = 100\ntsteps end\n"
            "physics begin\n  eqnset = euler\nphysics end\n"
        )
        (tmp_path / "cellsin.bin").write_bytes(b"\x00" * 100)
        (tmp_path / "nodesin.bin").write_bytes(b"\x00" * 100)
        (tmp_path / "cgrpsin.bin.1").write_bytes(b"\x00" * 100)
        (tmp_path / "C.dat").write_text("C data")
        (tmp_path / "mcfd.bc").write_text("boundary")
        (tmp_path / "mcfd.grp").write_text("groups")
        (tmp_path / "run_cfdpp.pbs").write_text("#!/bin/bash\n#PBS -N test\n")
        return tmp_path

    def test_missing_mcfd_inp_is_error(self, tmp_path):
        # 空目录
        from inp_tool.pbs import validate_base_case_dir
        issues = validate_base_case_dir(str(tmp_path))
        codes = {i.code for i in issues}
        assert "MISSING_MCFD_INP" in codes
        assert any(i.severity == "error" for i in issues if i.code == "MISSING_MCFD_INP")

    def test_complete_dir_no_issues(self, tmp_path):
        self._make_minimal_source(tmp_path)
        from inp_tool.pbs import validate_base_case_dir
        issues = validate_base_case_dir(str(tmp_path))
        # 0 个 error;允许 chemkin/restart 软提示
        errors = [i for i in issues if i.severity == "error"]
        assert errors == []

    def test_missing_grid_warns(self, tmp_path):
        self._make_minimal_source(tmp_path)
        (tmp_path / "cellsin.bin").unlink()
        from inp_tool.pbs import validate_base_case_dir
        issues = validate_base_case_dir(str(tmp_path))
        grid_issues = [i for i in issues if "GRID" in i.code]
        assert len(grid_issues) >= 1
        assert all(i.severity == "warning" for i in grid_issues)

    def test_missing_property_warns(self, tmp_path):
        self._make_minimal_source(tmp_path)
        (tmp_path / "C.dat").unlink()
        from inp_tool.pbs import validate_base_case_dir
        issues = validate_base_case_dir(str(tmp_path))
        prop_issues = [i for i in issues if "PROP" in i.code or "DAT" in i.code]
        assert len(prop_issues) >= 1
        assert all(i.severity == "warning" for i in prop_issues)

    def test_missing_pbs_warns(self, tmp_path):
        self._make_minimal_source(tmp_path)
        (tmp_path / "run_cfdpp.pbs").unlink()
        from inp_tool.pbs import validate_base_case_dir
        issues = validate_base_case_dir(str(tmp_path), pbs_enabled=True)
        pbs_issues = [i for i in issues if "PBS" in i.code or "PBS_TEMPLATE" in i.code]
        assert len(pbs_issues) >= 1
        assert all(i.severity == "warning" for i in pbs_issues)

    def test_pbs_enabled_false_skips_pbs_check(self, tmp_path):
        self._make_minimal_source(tmp_path)
        (tmp_path / "run_cfdpp.pbs").unlink()
        from inp_tool.pbs import validate_base_case_dir
        issues = validate_base_case_dir(str(tmp_path), pbs_enabled=False)
        pbs_issues = [i for i in issues if "PBS" in i.code]
        assert pbs_issues == []


class TestValidateBaseCaseBlocks:
    def _make_minimal_source_with_blocks(self, tmp_path, blocks=("tsteps", "physics", "chemkin", "restart")):
        """构造含指定 blocks 的 mcfd.inp(用 mcfd 真实格式: 'block begin' / 'block end')"""
        mcfd = tmp_path / "mcfd.inp"
        text = ""
        for b in blocks:
            text += f"{b} begin\n  key = 1\n{b} end\n"
        mcfd.write_text(text)
        return tmp_path

    def test_missing_required_block_warns(self, tmp_path):
        # v0.9.0:tsteps/physics 降为 warning(向后兼容老 fixture)
        self._make_minimal_source_with_blocks(tmp_path, blocks=("tsteps",))  # 缺 physics
        from inp_tool.pbs import validate_base_case_dir
        issues = validate_base_case_dir(str(tmp_path))
        block_issues = [i for i in issues if i.code.startswith("MISSING_BLOCK:")]
        # 缺 physics
        assert any("physics" in i.code for i in block_issues)
        # v0.9.0:warning(不阻断),为向后兼容
        assert all(i.severity == "warning" for i in block_issues if "physics" in i.code)

    def test_missing_warn_block_is_warning(self, tmp_path):
        self._make_minimal_source_with_blocks(tmp_path, blocks=("tsteps", "physics"))  # 缺 chemkin/restart
        from inp_tool.pbs import validate_base_case_dir
        issues = validate_base_case_dir(str(tmp_path))
        chemkin = [i for i in issues if "chemkin" in i.code]
        assert len(chemkin) == 1
        assert chemkin[0].severity == "warning"

    def test_all_blocks_present_no_block_issues(self, tmp_path):
        self._make_minimal_source_with_blocks(
            tmp_path, blocks=("tsteps", "physics", "chemkin", "restart")
        )
        from inp_tool.pbs import validate_base_case_dir
        issues = validate_base_case_dir(str(tmp_path))
        block_issues = [i for i in issues if i.code.startswith("MISSING_BLOCK:")]
        assert block_issues == []


class TestWritePbs:
    def test_replaces_pbs_n_line(self, tmp_path):
        template = tmp_path / "template.pbs"
        template.write_text(
            "#!/bin/bash\n"
            "#PBS -N OldName\n"
            "#PBS -l nodes=1:ppn=48\n"
            "#PBS -q q02\n"
            "echo hello\n"
        )
        from inp_tool.pbs import write_pbs
        out = tmp_path / "out.pbs"
        write_pbs(str(template), str(out), job_name="NewName")
        content = out.read_text()
        assert "#PBS -N NewName" in content
        assert "#PBS -l nodes=1:ppn=48" in content  # 其他行保留
        assert "#PBS -q q02" in content
        assert "echo hello" in content
        assert "OldName" not in content

    def test_appends_n_line_when_missing(self, tmp_path):
        template = tmp_path / "template.pbs"
        template.write_text(
            "#!/bin/bash\n"
            "#PBS -l nodes=1:ppn=48\n"
            "echo hi\n"
        )
        from inp_tool.pbs import write_pbs
        out = tmp_path / "out.pbs"
        write_pbs(str(template), str(out), job_name="NewName")
        content = out.read_text()
        assert "#PBS -N NewName" in content
        assert "#PBS -l nodes=1:ppn=48" in content

    def test_preserves_when_no_change(self, tmp_path):
        template = tmp_path / "template.pbs"
        template.write_text("#PBS -N SameName\n")
        from inp_tool.pbs import write_pbs
        out = tmp_path / "out.pbs"
        write_pbs(str(template), str(out), job_name="SameName")
        assert "#PBS -N SameName" in out.read_text()

    def test_template_not_found_raises(self, tmp_path):
        from inp_tool.pbs import write_pbs
        with pytest.raises(FileNotFoundError):
            write_pbs(str(tmp_path / "nope.pbs"), str(tmp_path / "out.pbs"), job_name="X")
