from mergecast.gitio import parse_diff


def test_parses_one_file_and_one_hunk():
    text = """\
diff --git a/src/app.py b/src/app.py
index 111..222 100644
--- a/src/app.py
+++ b/src/app.py
@@ -3,2 +3,3 @@ def f():
-old
+new
+extra
 context
"""
    files = parse_diff(text)
    assert len(files) == 1
    file = files[0]
    assert file.base_path == "src/app.py"
    assert file.path == "src/app.py"
    assert len(file.hunks) == 1
    hunk = file.hunks[0]
    assert (hunk.old_start, hunk.old_len, hunk.new_start, hunk.new_len) == (3, 2, 3, 3)
    assert hunk.lines == ("-old", "+new", "+extra")
    assert hunk.added == 3 and hunk.removed == 2
    assert file.churn == 5


def test_missing_counts_mean_one_line():
    text = """\
diff --git a/a.txt b/a.txt
--- a/a.txt
+++ b/a.txt
@@ -7 +7 @@
-a
+b
"""
    hunk = parse_diff(text)[0].hunks[0]
    assert (hunk.old_len, hunk.new_len) == (1, 1)
    assert hunk.span() == "line 7"


def test_pure_insertion_is_a_point():
    text = """\
diff --git a/a.txt b/a.txt
--- a/a.txt
+++ b/a.txt
@@ -10,0 +11,2 @@
+x
+y
"""
    hunk = parse_diff(text)[0].hunks[0]
    assert hunk.old_len == 0
    assert hunk.span() == "insert at 10"


def test_deleted_file_is_flagged():
    text = """\
diff --git a/old.txt b/old.txt
deleted file mode 100644
--- a/old.txt
+++ /dev/null
@@ -1,3 +0,0 @@
-a
-b
-c
"""
    file = parse_diff(text)[0]
    assert file.deleted is True
    assert file.added == 0 and file.removed == 3


def test_rename_uses_base_path_key():
    text = """\
diff --git a/lib/old_name.py b/lib/new_name.py
similarity index 90%
rename from lib/old_name.py
rename to lib/new_name.py
--- a/lib/old_name.py
+++ b/lib/new_name.py
@@ -2 +2 @@
-x
+y
"""
    file = parse_diff(text)[0]
    assert file.base_path == "lib/old_name.py"
    assert file.path == "lib/new_name.py"


def test_multiple_files_and_hunks():
    text = """\
diff --git a/a b/a
--- a/a
+++ b/a
@@ -1 +1 @@
-a
+A
@@ -20,2 +20,2 @@
-b
-B
diff --git a/b b/b
--- a/b
+++ b/b
@@ -5 +5 @@
-c
+C
"""
    files = parse_diff(text)
    assert [f.path for f in files] == ["a", "b"]
    assert [len(f.hunks) for f in files] == [2, 1]
    assert files[0].hunks[1].old_start == 20
