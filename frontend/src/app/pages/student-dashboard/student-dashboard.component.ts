import { Component, inject } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

@Component({
  selector: 'app-student-dashboard',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './student-dashboard.component.html',
})
export class StudentDashboardComponent {
  protected readonly denied = inject(ActivatedRoute).snapshot.queryParamMap.get('reason') === 'denied';
}
