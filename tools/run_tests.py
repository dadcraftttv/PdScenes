#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Runs the test suites in parallel and prints only failures and one summary line per suite.

    tools/run_tests.py                  everything (before a push)
    tools/run_tests.py quick glitch     only the test_patch.py sections whose title mentions a word, + Java tests
    tools/run_tests.py list             the test_patch.py section titles and how long each took last time

test_patch.py is one long script. It is cut into sections at its titled statements (a comment line right above a
statement). A section can run on its own: every earlier statement it needs (a helper, a variable it reads, a
function it calls and the variables that reads, the last statement that changed them) is run before it, found from
the code itself. Sections run in parallel worker processes (libpd is one instance per process), longest first, by how long each
took last time (tools/.test_costs.json), each section in a process of its own: Pd's [random] objects draw their
seeds from a per-process counter, so this way a section hears the same random choices in every run, full or quick.
"""
import ast, json, os, re, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
PY = os.path.join(TOOLS, ".venv", "bin", "python")
LIB = os.path.join(TOOLS, ".libpd", "libpd.so")
PATCH_TESTS = os.path.join(TOOLS, "test_patch.py")
COSTS = os.path.join(TOOLS, ".test_costs.json")
OTHER_PD = ["test_scene_loader.py", "test_scene_sensors.py", "test_rj_analysis.py", "test_bundled_scenes.py",
            "test_scene_helpers.py", "test_scene_graphics.py", "test_dcs.py"]
SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


# ---------------------------------------------------------------- reading the script
def bound_in(node):
    """Names a function, lambda or comprehension binds for itself."""
    out = set()
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        a = node.args
        out |= {x.arg for x in a.args + a.kwonlyargs + a.posonlyargs}
        out |= {x.arg for x in (a.vararg, a.kwarg) if x}
        body = node.body if isinstance(node.body, list) else [node.body]
        for st in body:
            for n in ast.walk(st):
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                    out.add(n.id)
                elif isinstance(n, (ast.Global, ast.Nonlocal)):
                    out -= set(n.names)
    else:
        for g in node.generators:
            out |= {n.id for n in ast.walk(g.target) if isinstance(n, ast.Name)}
    return out


def reads(node, local=frozenset()):
    """Global names a statement (or a function's body) reads."""
    out = set()
    def visit(n, loc):
        if isinstance(n, SCOPES):
            loc = loc | bound_in(n)
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id not in loc:
            out.add(n.id)
        if isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name) and n.target.id not in loc:
            out.add(n.target.id)                                     # (x += 1 reads x too)
        for c in ast.iter_child_nodes(n):
            visit(c, loc)
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        loc = set(local) | bound_in(node)
        for st in node.body:
            visit(st, loc)
        for d in node.args.defaults + node.args.kw_defaults:
            if d is not None:
                visit(d, set(local))
    else:
        visit(node, set(local))
    return out


def writes(st):
    """Global names a top-level statement sets or changes (x = .., x[..] = .., x.method(..), for x in ..)."""
    if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return {st.name}
    if isinstance(st, (ast.Import, ast.ImportFrom)):
        return {(a.asname or a.name).split(".")[0] for a in st.names}
    out = set()
    def base(t):
        while isinstance(t, (ast.Subscript, ast.Attribute, ast.Starred)):
            t = t.value
        return t.id if isinstance(t, ast.Name) else None
    def visit(n):
        if isinstance(n, SCOPES):
            return
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            out.add(n.id)
        if isinstance(n, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                for el in (t.elts if isinstance(t, ast.Tuple) else [t]):
                    b = base(el)
                    if b:
                        out.add(b)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):    # e.send(..), xs.append(..)
            b = base(n.func.value)
            if b:
                out.add(b)
        for c in ast.iter_child_nodes(n):
            visit(c)
    visit(st)
    return out


def load_script(path):
    src = open(path).read()
    lines = src.splitlines()
    body = ast.parse(src).body
    while body and re.search(r"ALL PASSED|sys\.exit", ast.get_source_segment(src, body[-1]) or ""):
        body = body[:-1]                                             # (the closing summary)
    stmts = []
    for st in body:
        title, j = [], st.lineno - 2
        while j >= 0 and lines[j].lstrip().startswith("#"):
            title.insert(0, lines[j].strip().lstrip("#").strip())
            j -= 1
        stmts.append(dict(node=st, title=" ".join(title), w=writes(st), r=reads(st)))
    # np.random.x(..) or os.path.y(..) changes nothing we follow: only plain assignments rebind modules and functions
    fixed = set().union(*(s["w"] for s in stmts if isinstance(s["node"], (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef))))
    for s in stmts:
        if not isinstance(s["node"], (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef)):
            direct = {n.id for n in ast.walk(s["node"]) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
            s["w"] = {x for x in s["w"] if x not in fixed or x in direct}
            s["wd"] = direct
        else:
            s["wd"] = s["w"]
    # what each top-level function reads, through the functions it calls
    funcs = {s["node"].name: set(s["r"]) for s in stmts if isinstance(s["node"], ast.FunctionDef)}
    changed = True
    while changed:
        changed = False
        for f, rs in funcs.items():
            more = set().union(*(funcs[g] for g in rs if g in funcs)) - rs
            if more:
                rs |= more
                changed = True
    for s in stmts:
        s["rt"] = s["r"] | set().union(*(funcs[g] for g in s["r"] if g in funcs))
    # sections: a new one at every titled statement
    sections, cur = [], None
    for i, s in enumerate(stmts):
        if s["title"] or cur is None:
            cur = dict(title=s["title"] or "(setup)", own=[])
            sections.append(cur)
        cur["own"].append(i)
        s["sec"] = len(sections) - 1
    return src, stmts, sections


def needed(stmts, own):
    """The statements to run for these: themselves, every def/import, and what they depend on."""
    always = {i for i, s in enumerate(stmts)
              if isinstance(s["node"], (ast.FunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)) or "fails" in s["w"]}
    need, todo = set(), list(set(own) | always)
    while todo:
        i = todo.pop()
        if i in need:
            continue
        need.add(i)
        for name in stmts[i]["rt"]:
            for j in range(i - 1, -1, -1):                          # the last earlier statement that set it
                if name in stmts[j]["w"]:
                    todo.append(j)
                    break
    return sorted(need)


# ---------------------------------------------------------------- one worker: runs some sections
def worker(path, lib, ids):
    sys.stdout.reconfigure(line_buffering=True)        # (Pd's C code prints to the same pipe: keep lines whole)
    src, stmts, sections = load_script(path)
    ids = [int(x) for x in ids]
    own_of = {i: k for k in ids for i in sections[k]["own"]}
    run = needed(stmts, [i for k in ids for i in sections[k]["own"]])
    sys.argv = [path, lib]
    sys.path.insert(0, os.path.dirname(path))
    g = {"__name__": "__main__", "__file__": path}
    times = {}
    import io, contextlib
    for i in run:
        t0 = time.perf_counter()
        mine = i in own_of
        before = g.get("fails", 0)
        try:
            # (a statement run only because a section needs what it sets: its own checks are that section's
            #  business, run under other random choices here, so they neither print nor count)
            with contextlib.redirect_stdout(sys.stdout if mine else io.StringIO()):
                exec(compile(ast.Module([stmts[i]["node"]], []), path, "exec"), g)
        except Exception as ex:
            print("FAIL: line %d raised %s: %s" % (stmts[i]["node"].lineno, type(ex).__name__, ex), flush=True)
            g["fails"] = g.get("fails", 0) + 1
        if not mine:
            g["fails"] = before
        k = own_of.get(i)
        if k is not None:
            times[k] = times.get(k, 0) + time.perf_counter() - t0
    print("@@fails %d" % g.get("fails", 0))
    print("@@times " + json.dumps({sections[k]["title"]: t for k, t in times.items()}))


# ---------------------------------------------------------------- the runner
def sh(cmd, cwd=ROOT, env=None):
    p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def run_patch_sections(pick, workers):
    _, stmts, sections = load_script(PATCH_TESTS)
    try:
        costs = json.load(open(COSTS))
    except (OSError, ValueError):
        costs = {}
    ks = [k for k in range(len(sections)) if pick(sections[k]["title"])]
    est = lambda k: costs.get(sections[k]["title"], 1 + 0.5 * len(sections[k]["own"]))
    # every section in a process of its own: Pd draws its random seeds from a per-process counter, so a section then
    # hears the same random choices whatever else runs (full or quick, any machine): its result is repeatable
    bins = [[est(k), [k]] for k in sorted(ks, key=est, reverse=True)]     # (longest first)
    def go(b):
        return sh([PY, os.path.abspath(__file__), "--worker", PATCH_TESTS, LIB] + [str(k) for k in sorted(b[1])])
    fails, out = 0, []
    with ThreadPoolExecutor(max(1, workers)) as ex:
        for b, (code, text) in zip(bins, ex.map(go, bins)):
            shown = len(out)
            for line in text.splitlines():
                if line.startswith("@@fails "):
                    fails += int(line.split()[1])
                    if int(line.split()[1]) and not any("FAIL" in l for l in text.splitlines()):
                        out.append("FAIL: [%s] counted a failure without a message; its last lines:" % sections[b[1][0]]["title"][:60])
                        out += ["    " + l for l in text.splitlines()[-6:]]
                elif line.startswith("@@times "):
                    costs.update(json.loads(line[8:]))
                elif "FAIL" in line or "Traceback" in line or "Error" in line[:40]:
                    out.append(line[line.find("FAIL"):] if "FAIL" in line else line)
            if code and not any(l.startswith("@@fails") for l in text.splitlines()):
                out.append("FAIL: a worker stopped: " + text.strip().splitlines()[-1] if text.strip() else "FAIL: a worker stopped")
                fails += 1
    json.dump(costs, open(COSTS, "w"), indent=0, sort_keys=True)
    return fails, out, len(ks)


def main():
    args = sys.argv[1:]
    if args[:1] == ["--worker"]:
        return worker(args[1], args[2], args[3:])
    if args[:1] == ["list"]:
        _, _, sections = load_script(PATCH_TESTS)
        try:
            costs = json.load(open(COSTS))
        except (OSError, ValueError):
            costs = {}
        for k, s in enumerate(sections):
            c = costs.get(s["title"])
            print("%3d %6s  %s" % (k, "%.1fs" % c if c is not None else "?", s["title"][:110]))
        return 0
    quick = args[:1] == ["quick"]
    words = [w.lower() for w in args[1:]] if quick else []
    workers = os.cpu_count() or 4
    t0 = time.time()
    env = dict(os.environ, JAVA_HOME=os.path.expanduser("~/.jdks/jbr-21.0.11"))
    env["PATH"] = env["JAVA_HOME"] + "/bin:" + env["PATH"]
    code, text = sh(["python3", "tools/make_patch.py"])
    if code:
        print("FAIL: make_patch.py\n" + text)
        return 1
    sh(["make", "-s", "-C", "dcs"])
    jobs = {"java": lambda: sh(["tools/javatests/run.sh"], env=env)}
    if not quick:
        jobs["desktop"] = lambda: sh(["desktop/test.sh"], env=env)
        for t in OTHER_PD:
            jobs[t] = (lambda t=t: sh([PY, os.path.join("tools", t), LIB]))
    results = {}
    with ThreadPoolExecutor(len(jobs) + 1) as ex:
        futs = {name: ex.submit(f) for name, f in jobs.items()}
        pick = (lambda title: any(w in title.lower() for w in words)) if quick else (lambda title: True)
        pf, pout, n = run_patch_sections(pick, workers)              # (the other suites are short: they share)
        for name, f in futs.items():
            results[name] = f.result()
    total = pf
    print("test_patch.py: %d sections, %s" % (n, "ALL PASSED" if not pf else "%d FAILED" % pf))
    for line in pout:
        print("  " + line)
    for name, (code, text) in results.items():
        bad = [l for l in text.splitlines() if l.startswith("FAIL") or "Exception" in l or "Traceback" in l or "error:" in l]
        ok = code == 0 and not bad
        total += 0 if ok else max(1, len(bad))
        print("%s: %s" % (name, "ALL PASSED" if ok else "FAILED"))
        for line in bad[:20]:
            print("  " + line)
    print("%s in %.0f s" % ("ALL PASSED" if not total else "%d FAILED" % total, time.time() - t0))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
