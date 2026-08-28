import unittest

import torch

from skwm_world_model import WMConfig, WorldModel, SKWMWorldModelAdapter


class RSSMRegressionTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(7)
        self.config = WMConfig(x_dim=4, a_dim=4, deter=16, stoch=5, hidden=12)
        self.model = WorldModel(self.config)

    def test_loss_is_finite_and_train_step_has_gradients(self):
        x = torch.randn(3, 6, self.config.x_dim)
        a = torch.randn(3, 6, self.config.a_dim)
        loss, logs = self.model.loss(x, a)
        self.assertTrue(torch.isfinite(loss))
        self.assertEqual(set(logs), {"pred", "dyn", "rep"})
        loss.backward()
        self.assertTrue(any(p.grad is not None for p in self.model.parameters()))

    def test_deterministic_imagine_is_repeatable(self):
        x0 = torch.randn(2, self.config.x_dim)
        actions = torch.randn(2, 4, self.config.a_dim)
        first = self.model.imagine(x0, actions, deterministic=True)
        second = self.model.imagine(x0, actions, deterministic=True)
        self.assertTrue(torch.allclose(first, second))
        self.assertEqual(tuple(first.shape), (2, 4, self.config.x_dim))

    def test_zero_horizon_returns_empty_rollout(self):
        x0 = torch.randn(2, self.config.x_dim)
        actions = torch.empty(2, 0, self.config.a_dim)
        result = self.model.imagine(x0, actions)
        self.assertEqual(tuple(result.shape), (2, 0, self.config.x_dim))

    def test_shape_errors_are_explicit(self):
        with self.assertRaises(ValueError):
            self.model.observe(torch.randn(2, 4), torch.randn(2, 3, self.config.a_dim))
        with self.assertRaises(ValueError):
            self.model.imagine(torch.randn(2, self.config.x_dim), torch.randn(3, 2, self.config.a_dim))

    def test_edge_interventions_are_not_limited_to_topic_index(self):
        adapter = SKWMWorldModelAdapter(self.model, device=torch.device("cpu"))
        control = {"edge_interventions": [("add", "x"), ("remove", "y")]}
        encoded = adapter.encode_action(control, topic_idx=0, all_topics=["topic"])
        self.assertEqual(encoded[0].item(), 0.0)
        self.assertEqual(encoded[2].item(), 1.0)
        self.assertEqual(encoded[3].item(), -1.0)


if __name__ == "__main__":
    unittest.main()
