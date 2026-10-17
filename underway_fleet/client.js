import { render } from '/plugins/underway_core/static/underway.js';

export default async function (shadow, ctx) {
  await render(shadow, ctx, 'fleet');
}
