export interface Health {
  status: string
  database: string
}

export class HealthError extends Error {
  health?: Health

  constructor(message: string, health?: Health) {
    super(message)
    this.health = health
  }
}
