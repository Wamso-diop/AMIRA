import subprocess

from tools import check_repo


def test_le_depot_est_sain():
    assert check_repo.problems() == []


def test_un_poids_est_refuse(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "x.txt").write_text("a")
    (tmp_path / "w.safetensors").write_text("a")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)
    assert len(check_repo.problems()) == 2
