"""
Regression tests for project pages and payment rendering.
"""

from datetime import datetime

from app.models import CapitalAllocation, EquityCapital, Project, ProjectCategory, ProjectItem, ProjectItemPayment, User


class TestProjectDetails:
    """Tests for project detail rendering."""

    def test_project_details_handles_payments_without_payment_date(self, client, app, db):
        """Project details should render even when some payments have no payment date."""
        with app.app_context():
            user = User(
                email='projects@example.com',
                name='Project Tester',
            )
            user.set_password('testpassword123')
            db.session.add(user)
            db.session.commit()

            project = Project(
                user_id=user.id,
                name='Home Renovation',
                funding_source='savings',
            )
            db.session.add(project)
            db.session.commit()

            item = ProjectItem(
                user_id=user.id,
                project_id=project.id,
                item_name='Tiles',
                cost=1000.0,
                item_type='expense',
            )
            db.session.add(item)
            income_item = ProjectItem(
                user_id=user.id,
                project_id=project.id,
                item_name='Client payment',
                cost=1500.0,
                item_type='income',
            )
            db.session.add(income_item)
            db.session.commit()

            db.session.add_all([
                ProjectItemPayment(
                    user_id=user.id,
                    project_item_id=item.id,
                    amount=250.0,
                    description='Paid installment',
                    is_paid=True,
                    payment_date=datetime(2026, 7, 10),
                    created_date=datetime(2026, 7, 10),
                ),
                ProjectItemPayment(
                    user_id=user.id,
                    project_item_id=item.id,
                    amount=150.0,
                    description='Pending installment',
                    is_paid=False,
                    payment_date=None,
                    created_date=datetime(2026, 7, 11),
                ),
            ])
            category = ProjectCategory(user_id=user.id, name='Renovation')
            db.session.add(category)
            db.session.flush()
            project.category_id = category.id
            equity = EquityCapital(user_id=user.id, category_id=category.id, initial_capital=2000)
            db.session.add(equity)
            db.session.flush()
            db.session.add_all([
                CapitalAllocation(user_id=user.id, equity_capital_id=equity.id, project_id=project.id,
                                  allocation_type='project_funding', funding_source='capital', amount=1000),
                CapitalAllocation(user_id=user.id, equity_capital_id=equity.id, project_id=project.id,
                                  allocation_type='project_funding', funding_source='retained', amount=500),
            ])
            db.session.commit()

            with client.session_transaction() as sess:
                sess['_user_id'] = str(user.id)
                sess['_fresh'] = True

            response = client.get(f'/projects/{project.id}')

            assert response.status_code == 200
            assert b'Paid installment' in response.data
            assert b'Pending installment' in response.data
            assert b'href="/projects"' in response.data
            assert b'Back to Projects' in response.data
            assert project.projected_profit == 500.0
            assert project.current_profit == -250.0
            assert b'Projected Gross Profit' in response.data
            assert b'Projected Net Profit' in response.data
            assert b'500.00' in response.data
            assert b'Current Gross Loss' in response.data
            assert b'Current Net Loss' in response.data
            assert b'250.00' in response.data
            assert b'Capital Funding' in response.data
            assert b'From capital' in response.data
            assert b'From retained' in response.data
            assert b'1,500.00' in response.data
            assert b'16.7%' in response.data
            assert project.total_capital_allocated == 1500
            assert project.capital_from_contributions == 1000
            assert project.capital_from_retained == 500
            assert project.capital_utilization == 16.7

            projects_response = client.get('/projects')

            assert projects_response.status_code == 200
            assert b'Current Net Profit' in projects_response.data
            assert b'Current Net Profit' in projects_response.data
            assert b'GHS 250.00' in projects_response.data

    def test_project_details_hides_capital_funding_without_allocations(self, client, app, db):
        with app.app_context():
            user = User(email='no-capital@example.com', name='No Capital Tester')
            user.set_password('testpassword123')
            db.session.add(user); db.session.flush()
            project = Project(user_id=user.id, name='Unfunded project', funding_source='savings')
            db.session.add(project); db.session.commit()
            with client.session_transaction() as sess:
                sess['_user_id'] = str(user.id)
                sess['_fresh'] = True

            response = client.get(f'/projects/{project.id}')

            assert response.status_code == 200
            assert b'Capital Funding' not in response.data
