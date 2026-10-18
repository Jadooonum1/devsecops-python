-- Demo helper: make three active loans overdue so the dashboard, the fine
-- workflow and the "overdue" alert have something to show. Not used by tests.
UPDATE loans SET borrowed_at = now() - interval '21 days', due_at = now() - interval '6 days'
WHERE id IN (SELECT id FROM loans WHERE status = 'active' ORDER BY id LIMIT 3);
