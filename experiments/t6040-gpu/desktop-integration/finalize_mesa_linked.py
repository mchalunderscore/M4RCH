#!/usr/bin/env python3
"""Record static ELF closure and a future loader recipe without loading Mesa."""
import argparse
import datetime
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import subprocess

KIT = Path(__file__).resolve().parent
ROOT = KIT.parents[2]
spec = importlib.util.spec_from_file_location("mesa_builder", KIT / "build_mesa_linked.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination")
    args = parser.parse_args()
    dest = Path(args.destination).resolve()
    dest.relative_to(ROOT / "out")
    prefix, build = dest / "prefix", dest / "build"
    initial = dest / "post-link.json" if (dest / "post-link.json").exists() else dest / "receipt.json"
    receipt = json.loads(initial.read_text())
    commands = json.loads((dest / "commands.json").read_text())

    def run(name, argv):
        log = dest / "logs" / (name + ".log")
        with log.open("w") as file:
            result = subprocess.run([str(x) for x in argv], cwd=ROOT,
                                    stdout=file, stderr=subprocess.STDOUT)
        commands.append({"phase": name, "argv": [str(x) for x in argv], "cwd": str(ROOT),
                         "exit": result.returncode, "log": str(log), **builder.pin(log)})
        if result.returncode:
            raise RuntimeError(f"{name}: exit {result.returncode}; see {log}")
        return log, log.read_text()

    cache_log, cache_text = run("elf-system-cache", ["ldconfig", "-p"])
    cache = {}
    for line in cache_text.splitlines():
        match = re.match(r"\s*(\S+)\s+\([^)]*\)\s+=>\s+(\S+)", line)
        if match:
            cache.setdefault(match[1], []).append(Path(match[2]))
    loader_env = {"__EGL_VENDOR_LIBRARY_FILENAMES": str(prefix / "share/glvnd/egl_vendor.d/50_mesa.json"),
                  "GBM_BACKENDS_PATH": str(prefix / "lib/gbm"),
                  "LD_LIBRARY_PATH": str(prefix / "lib")}
    recipe = dest / "future-loader.env"
    recipe.write_text("# Future recipe only. Never sourced or executed by this build.\n"
                      "# Requires a functioning T6040/G16S normal DRM stack and owner-selected render node.\n"
                      + "".join("export " + key + "=" + shlex.quote(value) + "\n" for key, value in loader_env.items())
                      + "# LIBGL_DRIVERS_PATH is unused here: EGL/GBM link the private libgallium directly.\n"
                      "# The no-op DRM shim is a build tool and is not placed in LD_PRELOAD.\n")
    loader_recipe = {"path": str(recipe), **builder.pin(recipe), "executed": False,
                     "environment": loader_env,
                     "LIBGL_DRIVERS_PATH": {"applicable": False,
                        "reason": "Selected Mesa links libgallium-26.3.0-devel.so directly; no per-driver DRI directory is installed"},
                     "gpu_startup_and_execution_gates_open": False}
    roots = [Path(item["path"]) for item in receipt["artifacts"]]
    roots.append(dest / "headless-smoke")
    pending = roots[:]
    seen, edges, nodes, unresolved = set(), [], [], []
    while pending:
        alias = pending.pop(0)
        path = alias.resolve()
        if path in seen:
            continue
        seen.add(path)
        log, elf = run("elf-closure-" + str(len(nodes)), ["readelf", "-h", "-d", "-n", str(path)])
        needed = re.findall(r"\(NEEDED\).*?\[(.*?)\]", elf)
        soname = re.findall(r"\(SONAME\).*?\[(.*?)\]", elf)
        runpaths = re.findall(r"\((?:RPATH|RUNPATH)\).*?\[(.*?)\]", elf)
        expanded = [Path(item.replace("$ORIGIN", str(path.parent)))
                    for value in runpaths for item in value.split(":") if item]
        nodes.append({"path": str(path), "root_artifact": path in [p.resolve() for p in roots],
                      **builder.pin(path), "soname": soname, "needed": needed,
                      "elf_class": re.search(r"Class:\s*(\S+)", elf)[1],
                      "machine": re.search(r"Machine:\s*(.*)", elf)[1].strip(),
                      "elf_evidence": str(log), "build_ids": re.findall(r"Build ID: (\S+)", elf)})
        for name in needed:
            candidates = [prefix / "lib" / name] + [p / name for p in expanded] + cache.get(name, [])
            match = next((p for p in candidates if p.is_file()), None)
            if match is None:
                unresolved.append({"from": str(path), "needed": name})
                continue
            edges.append({"from": str(path), "needed": name, "selected_path": str(match),
                          "resolved_path": str(match.resolve()), "private_prefix": match.is_relative_to(prefix)})
            pending.append(match)
    if unresolved:
        raise RuntimeError("Static dependency model has unresolved entries: " + str(unresolved))
    closure = {"schema": "m4rch.static-elf-dependency-closure.v1",
               "scope": "readelf-only resolution under the saved future private-prefix LD_LIBRARY_PATH plus system ldconfig cache; no loader execution",
               "actual_loaded_identity_proven": False, "cache_evidence": str(cache_log),
               "roots": [str(p) for p in roots], "nodes": nodes, "edges": edges,
               "unresolved": unresolved, "driver_loaded": False, "harness_executed": False}
    builder.save(dest / "elf-dependency-closure.json", closure)
    receipt["elf_dependency_closure"] = {"path": str(dest / "elf-dependency-closure.json"),
                                         **builder.pin(dest / "elf-dependency-closure.json"),
                                         "nodes": len(nodes), "edges": len(edges), "unresolved": 0,
                                         "actual_loaded_identity_proven": False}
    log, elf = run("harness-elf", ["readelf", "-h", "-d", "-n", str(dest / "headless-smoke")])
    receipt["harness"] = {"path": str(dest / "headless-smoke"), **builder.pin(dest / "headless-smoke"),
                          "elf_evidence": str(log), "executed": False,
                          "needed": re.findall(r"\(NEEDED\).*?\[(.*?)\]", elf)}
    receipt["loader_recipe"] = loader_recipe
    receipt["installed_symlinks"] = [{"path": str(p), "target": os.readlink(p),
                                       "resolved_path": str(p.resolve()), **builder.pin(p.resolve())}
                                      for p in sorted(prefix.rglob("*")) if p.is_symlink()]
    receipt["config_pins"] = [{"path": str(p), **builder.pin(p)} for p in [
        build / "meson-private/cmd_line.txt", build / "meson-info/intro-buildoptions.json",
        build / "meson-info/intro-dependencies.json", build / "meson-info/intro-targets.json",
        build / "build.ninja", build / "compile_commands.json",
        prefix / "share/glvnd/egl_vendor.d/50_mesa.json"]]
    run("link-recipes", ["ninja", "-C", str(build), "-t", "commands",
        "src/gallium/targets/dri/libgallium-26.3.0-devel.so", "src/gbm/backends/dri/dri_gbm.so",
        "src/egl/libEGL_mesa.so.0.0.0", "src/gbm/libgbm.so.1.0.0"])
    receipt["link_recipes"] = {"path": str(dest / "logs/link-recipes.log"),
                               **builder.pin(dest / "logs/link-recipes.log"),
                               "scope": "Generated Ninja recipes for targets that linked successfully in compile.log; no rebuild"}
    preserved = {}
    for name, before in receipt["baseline_tree_pins"].items():
        after = builder.manifest(builder.BASE / name)
        preserved[name] = after["tree_sha256"] == before
    receipt["baseline_preserved"] = preserved
    receipt["selected_metadata_preserved"] = all(builder.pin(builder.SELECTED / rel) ==
        {key: value for key, value in value.items() if key != "path"}
        for rel, value in receipt["selected_metadata"].items())
    receipt["staged_metadata_matches_selected"] = all(builder.pin(dest / "source" / rel) ==
        {key: value for key, value in value.items() if key != "path"}
        for rel, value in receipt["selected_metadata"].items())
    staged = builder.manifest(dest / "source")
    receipt["staged_source_unchanged_by_build"] = staged["tree_sha256"] == receipt["source_tree_sha256"]
    if not all(preserved.values()) or not all(receipt[key] for key in
        ("selected_metadata_preserved", "staged_metadata_matches_selected", "staged_source_unchanged_by_build")):
        raise RuntimeError("source/input preservation check failed")
    compile_log = (dest / "logs/compile.log").read_text()
    receipt["compiler_warnings"] = [line for line in compile_log.splitlines() if "warning:" in line]
    receipt["finalizer"] = {"path": str(Path(__file__).resolve()), **builder.pin(__file__)}
    receipt["helper_current"] = {"path": str(KIT / "build_mesa_linked.py"), **builder.pin(KIT / "build_mesa_linked.py")}
    receipt["status"] = "linked-preparation-only"
    receipt.pop("error", None)
    receipt["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    receipt["commands"] = commands
    builder.save(dest / "commands.json", commands)
    builder.save(dest / "receipt.json", receipt)
    builder.save(dest / "process.json", {"phase": "complete", "status": receipt["status"]})
    print(json.dumps({"status": receipt["status"], "elf_nodes": len(nodes), "unresolved": 0,
                      "baseline_preserved": preserved, "receipt": str(dest / "receipt.json")}))


if __name__ == "__main__":
    main()
