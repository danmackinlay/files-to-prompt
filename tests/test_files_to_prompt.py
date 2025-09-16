import os
import pytest
import re
import subprocess

from click.testing import CliRunner

from files_to_prompt.cli import cli


def _git(cmd, cwd):
    return subprocess.run(
        ["git", *cmd],
        cwd=cwd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def filenames_from_cxml(cxml_string):
    "Return set of filenames from <source>...</source> tags"
    return set(re.findall(r"<source>(.*?)</source>", cxml_string))


def test_basic_functionality(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir")
        with open("test_dir/file1.txt", "w") as f:
            f.write("Contents of file1")
        with open("test_dir/file2.txt", "w") as f:
            f.write("Contents of file2")

        result = runner.invoke(cli, ["test_dir"])
        assert result.exit_code == 0
        assert "test_dir/file1.txt" in result.output
        assert "Contents of file1" in result.output
        assert "test_dir/file2.txt" in result.output
        assert "Contents of file2" in result.output


def test_include_hidden(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir")
        with open("test_dir/.hidden.txt", "w") as f:
            f.write("Contents of hidden file")

        result = runner.invoke(cli, ["test_dir"])
        assert result.exit_code == 0
        assert "test_dir/.hidden.txt" not in result.output

        result = runner.invoke(cli, ["test_dir", "--include-hidden"])
        assert result.exit_code == 0
        assert "test_dir/.hidden.txt" in result.output
        assert "Contents of hidden file" in result.output


def test_ignore_gitignore(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir")
        os.makedirs("test_dir/nested_include")
        os.makedirs("test_dir/nested_ignore")
        with open("test_dir/.gitignore", "w") as f:
            f.write("ignored.txt")
        with open("test_dir/ignored.txt", "w") as f:
            f.write("This file should be ignored")
        with open("test_dir/included.txt", "w") as f:
            f.write("This file should be included")
        with open("test_dir/nested_include/included2.txt", "w") as f:
            f.write("This nested file should be included")
        with open("test_dir/nested_ignore/.gitignore", "w") as f:
            f.write("nested_ignore.txt")
        with open("test_dir/nested_ignore/nested_ignore.txt", "w") as f:
            f.write("This nested file should not be included")
        with open("test_dir/nested_ignore/actually_include.txt", "w") as f:
            f.write("This nested file should actually be included")

        result = runner.invoke(cli, ["test_dir", "-c"])
        assert result.exit_code == 0
        filenames = filenames_from_cxml(result.output)

        assert filenames == {
            "test_dir/included.txt",
            "test_dir/nested_include/included2.txt",
            "test_dir/nested_ignore/actually_include.txt",
        }

        result2 = runner.invoke(cli, ["test_dir", "-c", "--ignore-gitignore"])
        assert result2.exit_code == 0
        filenames2 = filenames_from_cxml(result2.output)

        assert filenames2 == {
            "test_dir/included.txt",
            "test_dir/ignored.txt",
            "test_dir/nested_include/included2.txt",
            "test_dir/nested_ignore/nested_ignore.txt",
            "test_dir/nested_ignore/actually_include.txt",
        }


def test_multiple_paths(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir1")
        with open("test_dir1/file1.txt", "w") as f:
            f.write("Contents of file1")
        os.makedirs("test_dir2")
        with open("test_dir2/file2.txt", "w") as f:
            f.write("Contents of file2")
        with open("single_file.txt", "w") as f:
            f.write("Contents of single file")

        result = runner.invoke(cli, ["test_dir1", "test_dir2", "single_file.txt"])
        assert result.exit_code == 0
        assert "test_dir1/file1.txt" in result.output
        assert "Contents of file1" in result.output
        assert "test_dir2/file2.txt" in result.output
        assert "Contents of file2" in result.output
        assert "single_file.txt" in result.output
        assert "Contents of single file" in result.output


def test_ignore_patterns(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir", exist_ok=True)
        with open("test_dir/file_to_ignore.txt", "w") as f:
            f.write("This file should be ignored due to ignore patterns")
        with open("test_dir/file_to_include.txt", "w") as f:
            f.write("This file should be included")

        result = runner.invoke(cli, ["test_dir", "--ignore", "*.txt"])
        assert result.exit_code == 0
        assert "test_dir/file_to_ignore.txt" not in result.output
        assert "This file should be ignored due to ignore patterns" not in result.output
        assert "test_dir/file_to_include.txt" not in result.output

        os.makedirs("test_dir/test_subdir", exist_ok=True)
        with open("test_dir/test_subdir/any_file.txt", "w") as f:
            f.write("This entire subdirectory should be ignored due to ignore patterns")
        result = runner.invoke(cli, ["test_dir", "--ignore", "*subdir*"])
        assert result.exit_code == 0
        assert "test_dir/test_subdir/any_file.txt" not in result.output
        assert (
            "This entire subdirectory should be ignored due to ignore patterns"
            not in result.output
        )
        assert "test_dir/file_to_include.txt" in result.output
        assert "This file should be included" in result.output
        assert "This file should be included" in result.output

        result = runner.invoke(
            cli, ["test_dir", "--ignore", "*subdir*", "--ignore-files-only"]
        )
        assert result.exit_code == 0
        assert "test_dir/test_subdir/any_file.txt" in result.output

        result = runner.invoke(cli, ["test_dir", "--ignore", ""])


def test_specific_extensions(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        # Write one.txt one.py two/two.txt two/two.py three.md
        os.makedirs("test_dir/two")
        with open("test_dir/one.txt", "w") as f:
            f.write("This is one.txt")
        with open("test_dir/one.py", "w") as f:
            f.write("This is one.py")
        with open("test_dir/two/two.txt", "w") as f:
            f.write("This is two/two.txt")
        with open("test_dir/two/two.py", "w") as f:
            f.write("This is two/two.py")
        with open("test_dir/three.md", "w") as f:
            f.write("This is three.md")

        # Try with -e py -e md
        result = runner.invoke(cli, ["test_dir", "-e", "py", "-e", "md"])
        assert result.exit_code == 0
        assert ".txt" not in result.output
        assert "test_dir/one.py" in result.output
        assert "test_dir/two/two.py" in result.output
        assert "test_dir/three.md" in result.output


def test_mixed_paths_with_options(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir")
        with open("test_dir/.gitignore", "w") as f:
            f.write("ignored_in_gitignore.txt\n.hidden_ignored_in_gitignore.txt")
        with open("test_dir/ignored_in_gitignore.txt", "w") as f:
            f.write("This file should be ignored by .gitignore")
        with open("test_dir/.hidden_ignored_in_gitignore.txt", "w") as f:
            f.write("This hidden file should be ignored by .gitignore")
        with open("test_dir/included.txt", "w") as f:
            f.write("This file should be included")
        with open("test_dir/.hidden_included.txt", "w") as f:
            f.write("This hidden file should be included")
        with open("single_file.txt", "w") as f:
            f.write("Contents of single file")

        result = runner.invoke(cli, ["test_dir", "single_file.txt"])
        assert result.exit_code == 0
        assert "test_dir/ignored_in_gitignore.txt" not in result.output
        assert "test_dir/.hidden_ignored_in_gitignore.txt" not in result.output
        assert "test_dir/included.txt" in result.output
        assert "test_dir/.hidden_included.txt" not in result.output
        assert "single_file.txt" in result.output
        assert "Contents of single file" in result.output

        result = runner.invoke(cli, ["test_dir", "single_file.txt", "--include-hidden"])
        assert result.exit_code == 0
        assert "test_dir/ignored_in_gitignore.txt" not in result.output
        assert "test_dir/.hidden_ignored_in_gitignore.txt" not in result.output
        assert "test_dir/included.txt" in result.output
        assert "test_dir/.hidden_included.txt" in result.output
        assert "single_file.txt" in result.output
        assert "Contents of single file" in result.output

        result = runner.invoke(
            cli, ["test_dir", "single_file.txt", "--ignore-gitignore"]
        )
        assert result.exit_code == 0
        assert "test_dir/ignored_in_gitignore.txt" in result.output
        assert "test_dir/.hidden_ignored_in_gitignore.txt" not in result.output
        assert "test_dir/included.txt" in result.output
        assert "test_dir/.hidden_included.txt" not in result.output
        assert "single_file.txt" in result.output
        assert "Contents of single file" in result.output

        result = runner.invoke(
            cli,
            ["test_dir", "single_file.txt", "--ignore-gitignore", "--include-hidden"],
        )
        assert result.exit_code == 0
        assert "test_dir/ignored_in_gitignore.txt" in result.output
        assert "test_dir/.hidden_ignored_in_gitignore.txt" in result.output
        assert "test_dir/included.txt" in result.output
        assert "test_dir/.hidden_included.txt" in result.output
        assert "single_file.txt" in result.output
        assert "Contents of single file" in result.output


def test_binary_file_warning(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir")
        with open("test_dir/binary_file.bin", "wb") as f:
            f.write(b"\xff")
        with open("test_dir/text_file.txt", "w") as f:
            f.write("This is a text file")

        result = runner.invoke(cli, ["test_dir"])
        assert result.exit_code == 0

        # Check output and stderr (may be combined)
        output = result.output or ""
        stderr = getattr(result, "stderr", "") or ""
        combined = output + stderr

        assert "test_dir/text_file.txt" in output
        assert "This is a text file" in output
        assert "\ntest_dir/binary_file.bin" not in output
        assert (
            "Warning: Skipping file test_dir/binary_file.bin due to UnicodeDecodeError"
            in combined
        )


@pytest.mark.parametrize(
    "args", (["test_dir"], ["test_dir/file1.txt", "test_dir/file2.txt"])
)
def test_xml_format_dir(tmpdir, args):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir")
        with open("test_dir/file1.txt", "w") as f:
            f.write("Contents of file1.txt")
        with open("test_dir/file2.txt", "w") as f:
            f.write("Contents of file2.txt")
        result = runner.invoke(cli, args + ["--cxml"])
        assert result.exit_code == 0
        actual = result.output
        expected = """
<documents>
<document index="1">
<source>test_dir/file1.txt</source>
<document_content>
Contents of file1.txt
</document_content>
</document>
<document index="2">
<source>test_dir/file2.txt</source>
<document_content>
Contents of file2.txt
</document_content>
</document>
</documents>
"""
        assert expected.strip() == actual.strip()


@pytest.mark.parametrize("arg", ("-o", "--output"))
def test_output_option(tmpdir, arg):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir")
        with open("test_dir/file1.txt", "w") as f:
            f.write("Contents of file1.txt")
        with open("test_dir/file2.txt", "w") as f:
            f.write("Contents of file2.txt")
        output_file = "output.txt"
        result = runner.invoke(
            cli, ["test_dir", arg, output_file], catch_exceptions=False
        )
        assert result.exit_code == 0
        assert not result.output
        with open(output_file, "r") as f:
            actual = f.read()
        expected = """
test_dir/file1.txt
---
Contents of file1.txt

---
test_dir/file2.txt
---
Contents of file2.txt

---
"""
        assert expected.strip() == actual.strip()


def test_line_numbers(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir")
        test_content = "First line\nSecond line\nThird line\nFourth line\n"
        with open("test_dir/multiline.txt", "w") as f:
            f.write(test_content)

        result = runner.invoke(cli, ["test_dir"])
        assert result.exit_code == 0
        assert "1  First line" not in result.output
        assert test_content in result.output

        result = runner.invoke(cli, ["test_dir", "-n"])
        assert result.exit_code == 0
        assert "1  First line" in result.output
        assert "2  Second line" in result.output
        assert "3  Third line" in result.output
        assert "4  Fourth line" in result.output

        result = runner.invoke(cli, ["test_dir", "--line-numbers"])
        assert result.exit_code == 0
        assert "1  First line" in result.output
        assert "2  Second line" in result.output
        assert "3  Third line" in result.output
        assert "4  Fourth line" in result.output


@pytest.mark.parametrize(
    "input,extra_args",
    (
        ("test_dir1/file1.txt\ntest_dir2/file2.txt", []),
        ("test_dir1/file1.txt\ntest_dir2/file2.txt", []),
        ("test_dir1/file1.txt\0test_dir2/file2.txt", ["--null"]),
        ("test_dir1/file1.txt\0test_dir2/file2.txt", ["-0"]),
    ),
)
def test_reading_paths_from_stdin(tmpdir, input, extra_args):
    runner = CliRunner()
    with tmpdir.as_cwd():
        # Create test files
        os.makedirs("test_dir1")
        os.makedirs("test_dir2")
        with open("test_dir1/file1.txt", "w") as f:
            f.write("Contents of file1")
        with open("test_dir2/file2.txt", "w") as f:
            f.write("Contents of file2")

        # Test space-separated paths from stdin
        result = runner.invoke(cli, args=extra_args, input=input)
        assert result.exit_code == 0
        assert "test_dir1/file1.txt" in result.output
        assert "Contents of file1" in result.output
        assert "test_dir2/file2.txt" in result.output
        assert "Contents of file2" in result.output


def test_paths_from_arguments_and_stdin(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        # Create test files
        os.makedirs("test_dir1")
        os.makedirs("test_dir2")
        with open("test_dir1/file1.txt", "w") as f:
            f.write("Contents of file1")
        with open("test_dir2/file2.txt", "w") as f:
            f.write("Contents of file2")

        # Test paths from arguments and stdin
        result = runner.invoke(
            cli,
            args=["test_dir1"],
            input="test_dir2/file2.txt",
        )
        assert result.exit_code == 0
        assert "test_dir1/file1.txt" in result.output
        assert "Contents of file1" in result.output
        assert "test_dir2/file2.txt" in result.output
        assert "Contents of file2" in result.output


@pytest.mark.parametrize("option", ("-m", "--markdown"))
def test_markdown(tmpdir, option):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir")
        with open("test_dir/python.py", "w") as f:
            f.write("This is python")
        with open("test_dir/python_with_quad_backticks.py", "w") as f:
            f.write("This is python with ```` in it already")
        with open("test_dir/code.js", "w") as f:
            f.write("This is javascript")
        with open("test_dir/code.unknown", "w") as f:
            f.write("This is an unknown file type")
        result = runner.invoke(cli, ["test_dir", option])
        assert result.exit_code == 0
        actual = result.output
        expected = (
            "test_dir/code.js\n"
            "```javascript\n"
            "This is javascript\n"
            "```\n"
            "test_dir/code.unknown\n"
            "```\n"
            "This is an unknown file type\n"
            "```\n"
            "test_dir/python.py\n"
            "```python\n"
            "This is python\n"
            "```\n"
            "test_dir/python_with_quad_backticks.py\n"
            "`````python\n"
            "This is python with ```` in it already\n"
            "`````\n"
        )
        assert expected.strip() == actual.strip()


def test_since_requires_git_repo(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        # Not a repo
        result = runner.invoke(cli, ["--since", "HEAD"])
        assert result.exit_code != 0
        # either output or stderr can contain the message depending on click version
        combined = (result.output or "") + (getattr(result, "stderr", "") or "")
        assert "not a git repository" in combined


def test_since_head_changes_and_untracked(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        _git(["init", "."], os.getcwd())
        # base commit
        with open("a.txt", "w") as f:
            f.write("v1\n")
        _git(["add", "a.txt"], os.getcwd())
        _git(
            [
                "-c",
                "user.name=T",
                "-c",
                "user.email=t@example.com",
                "commit",
                "-m",
                "base",
            ],
            os.getcwd(),
        )

        # modify tracked + add untracked
        with open("a.txt", "w") as f:
            f.write("v2\n")
        with open("b.txt", "w") as f:
            f.write("new file\n")

        result = runner.invoke(cli, ["--since", "HEAD"])
        assert result.exit_code == 0
        # repo-root-relative paths
        assert "a.txt" in result.output
        assert "b.txt" in result.output
        assert "v2" in result.output
        assert "new file" in result.output


def test_since_respects_filters(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        _git(["init", "."], os.getcwd())

        # Create .gitignore that ignores *.log (Git-level ignores)
        with open(".gitignore", "w") as f:
            f.write("*.log\n")
        _git(["add", ".gitignore"], os.getcwd())
        _git(
            [
                "-c",
                "user.name=T",
                "-c",
                "user.email=t@example.com",
                "commit",
                "-m",
                "gi",
            ],
            os.getcwd(),
        )

        # base commit
        os.makedirs("pkg", exist_ok=True)
        with open("pkg/keep.py", "w") as f:
            f.write("base\n")
        _git(["add", "pkg/keep.py"], os.getcwd())
        _git(
            [
                "-c",
                "user.name=T",
                "-c",
                "user.email=t@example.com",
                "commit",
                "-m",
                "base",
            ],
            os.getcwd(),
        )

        # changes after base
        with open("pkg/keep.py", "w") as f:
            f.write("changed\n")
        with open("note.md", "w") as f:
            f.write("doc\n")
        with open("tmp.log", "w") as f:
            f.write("ignored by gitignore\n")
        os.makedirs(".hidden_dir", exist_ok=True)
        with open(".hidden_dir/x.txt", "w") as f:
            f.write("hidden\n")

        # 1) extension filter: only md, hidden excluded by default, gitignored excluded by Git
        result = runner.invoke(cli, ["--since", "HEAD", "-e", "md"])
        assert result.exit_code == 0
        out = result.output
        assert "note.md" in out
        assert "pkg/keep.py" not in out
        assert "tmp.log" not in out
        assert ".hidden_dir/x.txt" not in out

        # 2) include hidden: now hidden file appears, but gitignored (*.log) still excluded
        result2 = runner.invoke(cli, ["--since", "HEAD", "--include-hidden"])
        assert result2.exit_code == 0
        out2 = result2.output
        assert "pkg/keep.py" in out2
        assert "note.md" in out2
        assert ".hidden_dir/x.txt" in out2
        assert "tmp.log" not in out2  # still excluded by Git ignore rules

        # 3) tool-level ignore patterns: ignore *.md at the tool layer
        result3 = runner.invoke(cli, ["--since", "HEAD", "--ignore", "*.md"])
        assert result3.exit_code == 0
        out3 = result3.output
        assert "note.md" not in out3
        assert "pkg/keep.py" in out3


def test_since_ignores_ignore_gitignore_flag_with_warning(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        _git(["init", "."], os.getcwd())
        with open(".gitignore", "w") as f:
            f.write("*.log\n")
        _git(["add", ".gitignore"], os.getcwd())
        _git(
            [
                "-c",
                "user.name=T",
                "-c",
                "user.email=t@example.com",
                "commit",
                "-m",
                "gi",
            ],
            os.getcwd(),
        )

        # base commit
        with open("a.py", "w") as f:
            f.write("base\n")
        _git(["add", "a.py"], os.getcwd())
        _git(
            [
                "-c",
                "user.name=T",
                "-c",
                "user.email=t@example.com",
                "commit",
                "-m",
                "base",
            ],
            os.getcwd(),
        )

        # change tracked; create ignored untracked
        with open("a.py", "w") as f:
            f.write("changed\n")
        with open("build.log", "w") as f:
            f.write("ignored by git\n")

        result = runner.invoke(cli, ["--since", "HEAD", "--ignore-gitignore"])
        # Should warn and still exclude the .log file
        # Check both output and stderr for the warning
        combined = (result.output or "") + (getattr(result, "stderr", "") or "")
        assert "ignored with --since" in combined
        assert "a.py" in result.output
        assert "build.log" not in result.output


def test_since_respects_path_restrictions(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        _git(["init", "."], os.getcwd())

        os.makedirs("src", exist_ok=True)
        os.makedirs("tests", exist_ok=True)

        with open("src/a.py", "w") as f:
            f.write("v1\n")
        _git(["add", "src/a.py"], os.getcwd())
        _git(
            [
                "-c",
                "user.name=T",
                "-c",
                "user.email=t@example.com",
                "commit",
                "-m",
                "base",
            ],
            os.getcwd(),
        )

        with open("src/a.py", "w") as f:
            f.write("v2\n")
        with open("tests/t_test.py", "w") as f:
            f.write("new\n")

        # restrict to src/ only
        result = runner.invoke(cli, ["--since", "HEAD", "src"])
        assert result.exit_code == 0
        out = result.output
        assert "src/a.py" in out
        assert "tests/t_test.py" not in out
