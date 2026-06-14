import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import checkin
from checkin import generate_balance_hash
from utils.config import AccountConfig, AppConfig, ProviderConfig


def test_balance_hash_changes_when_quota_changes():
	before = {'account_1': {'quota': 100.0, 'used': 20.0}}
	after = {'account_1': {'quota': 125.0, 'used': 20.0}}

	assert generate_balance_hash(before) != generate_balance_hash(after)


def test_balance_hash_changes_when_used_quota_changes():
	before = {'account_1': {'quota': 100.0, 'used': 20.0}}
	after = {'account_1': {'quota': 100.0, 'used': 21.0}}

	assert generate_balance_hash(before) != generate_balance_hash(after)


def test_balance_hash_is_stable_for_equivalent_balances():
	left = {
		'account_2': {'quota': 50.0, 'used': 1.0},
		'account_1': {'quota': 100.0, 'used': 20.0},
	}
	right = {
		'account_1': {'used': 20.0, 'quota': 100.0},
		'account_2': {'used': 1.0, 'quota': 50.0},
	}

	assert generate_balance_hash(left) == generate_balance_hash(right)


@pytest.mark.asyncio
async def test_successful_check_in_with_balance_change_does_not_notify(monkeypatch, tmp_path):
	previous_balances = {'account_1': {'quota': 100.0, 'used': 20.0}}
	(tmp_path / checkin.BALANCE_HASH_FILE).write_text(generate_balance_hash(previous_balances), encoding='utf-8')
	monkeypatch.chdir(tmp_path)

	account = AccountConfig(cookies={'session': 'value'}, provider='anyrouter', name='Account 1')
	app_config = AppConfig(providers={'anyrouter': ProviderConfig(name='anyrouter', domain='https://example.com')})
	sent_messages = []

	async def fake_check_in_account(_account, _account_index, _app_config):
		return (
			True,
			{'success': True, 'quota': 100.0, 'used_quota': 20.0},
			{'success': True, 'quota': 125.0, 'used_quota': 20.0, 'display': 'balance changed'},
		)

	monkeypatch.setattr(checkin.AppConfig, 'load_from_env', classmethod(lambda cls: app_config))
	monkeypatch.setattr(checkin, 'load_accounts_config', lambda: [account])
	monkeypatch.setattr(checkin, 'check_in_account', fake_check_in_account)
	monkeypatch.setattr(checkin.notify, 'push_message', lambda *args, **kwargs: sent_messages.append((args, kwargs)))

	with pytest.raises(SystemExit) as exc_info:
		await checkin.main()

	assert exc_info.value.code == 0
	assert sent_messages == []
