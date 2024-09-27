# Copyright (c) 2024, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import multiprocessing
import os
import subprocess
import time
from typing import Optional

from data.extract import get_shard_list


def execute_cmd(cmd_tuple: tuple):
    cmd, task_id = cmd_tuple
    start_time = time.time()
    print(f" ****** Task ID {task_id:02d} starts to preprocess {os.path.basename(cmd[2])}...")

    subprocess.check_call(cmd)
    print(f" ****** Task ID {task_id:02d} finished preprocessing {os.path.basename(cmd[2])}...")
    print(f" ****** Task ID {task_id:02d} time elapsed {(time.time() - start_time) / 60:.2f} min.")


def preprocess_data(
    data_dir: str,
    output_dir: str,
    dataset_impl: str = "mmap",
    tokenizer_type: str = "GPT2BPETokenizer",
    tokenizer_library: str = "megatron",
    vocab_file_path: Optional[str] = None,
    merges_file_path: Optional[str] = None,
    num_tasks: Optional[int] = None,
    task_id: Optional[int] = None,
    extra_args: Optional[list[str]] = None,
):
    if not num_tasks:
        if "SLURM_ARRAY_TASK_COUNT" in os.environ:
            num_tasks = int(os.environ["SLURM_ARRAY_TASK_COUNT"])
            task_id = int(os.environ["SLURM_ARRAY_TASK_ID"])
        else:
            num_tasks = 1
            task_id = 0
    shards_to_extract = get_shard_list(data_dir, num_tasks, extension="*.jsonl")
    shard_files = shards_to_extract[task_id]
    cmd = [
        "python",
        "/opt/NeMo/scripts/nlp_language_modeling/preprocess_data_for_megatron.py",
    ]

    os.makedirs(output_dir, exist_ok=True)
    final_cmds = []
    for split in shard_files:
        if not split:  # Remove empty split
            continue

        output_arg = os.path.join(output_dir, os.path.basename(split))

        flags = [
            f"--input={split}",
            f"--output-prefix={output_arg}",
            f"--dataset-impl={dataset_impl}",
            f"--tokenizer-library={tokenizer_library}",
            f"--tokenizer-type={tokenizer_type}",
        ]

        if vocab_file_path and merges_file_path:
            flags += [
                f"--vocab={vocab_file_path}",
                f"--merge-file={merges_file_path}",
                "--append-eod",
            ]

        final_cmd = cmd + flags
        if extra_args:
            final_cmd += extra_args
        final_cmds.append((final_cmd, task_id))

    with multiprocessing.Pool(multiprocessing.cpu_count()) as pool:
        pool.map(
            execute_cmd,
            final_cmds
        )