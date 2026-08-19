# -*- coding: utf-8 -*-
"""push_via_api.py — 通过 GitHub REST API 推送 (绕过被阻断的 github.com git 线路)
================================================================================
背景: 本机到 github.com 的 git 协议被网络限速 (TCP 通但 0 字节),
      api.github.com 线路正常 → 用 API 创建 blob/tree/commit/ref 完成推送。

用法:
  1. 设置 token 环境变量 (Fine-grained token, 仓库读写权限):
       set GITHUB_TOKEN=github_pat_xxx        (PowerShell)
       export GITHUB_TOKEN=github_pat_xxx     (bash)
  2. python push_via_api.py --repo natebrashaf-rgb/skwm-world-model \
        --dir 要推送的本地目录 --prefix experiments --gitignore .gitignore
  3. 脚本自动: 取远端 HEAD → 传文件 → 建 commit → 更新 main → 验证

注意: 推送的是"目录内容", 与本地 git 提交 (924f1a1) 内容一致;
      仅用于当前网络受限的临时场景, 网络恢复后建议仍用 git push 保持历史完整。
"""
import argparse
import base64
import json
import os
import sys

import requests

API = "https://api.github.com"


def gh(session, method, url, **kw):
    r = session.request(method, url, timeout=60, **kw)
    if r.status_code >= 400:
        raise RuntimeError(f"{method} {url} -> {r.status_code}: {r.text[:300]}")
    return r.json() if r.content else {}


def collect_files(root, prefix, skip=()):
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ("__pycache__",)]
        for fn in filenames:
            if any(fn.startswith(s) for s in skip):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace("\\", "/")
            files.append((f"{prefix}/{rel}" if prefix else rel, full))
    return sorted(files)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="owner/repo")
    ap.add_argument("--dir", required=True, help="要推送的本地目录")
    ap.add_argument("--prefix", default="", help="仓库内目标路径前缀 (如 experiments)")
    ap.add_argument("--commit-msg", default="feat: 实验流水线 (API 推送)")
    ap.add_argument("--branch", default="main")
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("错误: 未设置 GITHUB_TOKEN 环境变量")
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}",
                            "Accept": "application/vnd.github+json"})

    # 1. 远端 HEAD + base tree
    ref = gh(session, "GET", f"{API}/repos/{args.repo}/git/ref/heads/{args.branch}")
    head_sha = ref["object"]["sha"]
    head = gh(session, "GET", f"{API}/repos/{args.repo}/git/commits/{head_sha}")
    base_tree = head["tree"]["sha"]
    print(f"[1/5] 远端 HEAD={head_sha[:8]} base_tree={base_tree[:8]}")

    # 2. 上传文件 blobs
    files = collect_files(args.dir, args.prefix)
    print(f"[2/5] 上传 {len(files)} 个文件 ...")
    tree_items = []
    for path, full in files:
        with open(full, "rb") as f:
            content = f.read()
        blob = gh(session, "POST", f"{API}/repos/{args.repo}/git/blobs",
                  json={"content": base64.b64encode(content).decode(),
                        "encoding": "base64"})
        tree_items.append({"path": path, "mode": "100644", "type": "blob",
                           "sha": blob["sha"]})
        print(f"      {path} ({len(content)} B)")

    # 3. 新 tree (挂在远端 base_tree 上, 不影响其他文件)
    new_tree = gh(session, "POST", f"{API}/repos/{args.repo}/git/trees",
                  json={"base_tree": base_tree, "tree": tree_items})
    print(f"[3/5] 新 tree={new_tree['sha'][:8]}")

    # 4. commit
    commit = gh(session, "POST", f"{API}/repos/{args.repo}/git/commits",
                json={"message": args.commit_msg, "tree": new_tree["sha"],
                      "parents": [head_sha]})
    print(f"[4/5] commit={commit['sha'][:8]}")

    # 5. 更新分支
    gh(session, "PATCH", f"{API}/repos/{args.repo}/git/refs/heads/{args.branch}",
       json={"sha": commit["sha"], "force": False})
    print(f"[5/5] 分支 {args.branch} 已更新 → {commit['sha']}")

    # 验证
    verify = gh(session, "GET", f"{API}/repos/{args.repo}/git/ref/heads/{args.branch}")
    ok = verify["object"]["sha"] == commit["sha"]
    print(f"[验证] 远端 main = {verify['object']['sha'][:8]} | 一致: {ok}")
    print("\n✅ 推送完成。网页端刷新即可看到 experiments/ 目录。")


if __name__ == "__main__":
    main()
