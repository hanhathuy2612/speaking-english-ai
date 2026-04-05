import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';

export type BreadcrumbLink = string | readonly unknown[];

export interface BreadcrumbItem {
  label: string;
  link?: BreadcrumbLink;
}

@Component({
  selector: 'app-breadcrumb',
  imports: [RouterLink],
  templateUrl: './breadcrumb.component.html',
  styleUrl: './breadcrumb.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BreadcrumbComponent {
  items = input.required<readonly BreadcrumbItem[]>();
}
