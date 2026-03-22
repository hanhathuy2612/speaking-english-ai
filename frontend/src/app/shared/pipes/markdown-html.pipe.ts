import { Pipe, PipeTransform, inject } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { marked } from 'marked';

marked.setOptions({ gfm: true, breaks: true });

@Pipe({
  name: 'markdownHtml',
  standalone: true,
})
export class MarkdownHtmlPipe implements PipeTransform {
  private readonly sanitizer = inject(DomSanitizer);

  transform(value: string | null | undefined): SafeHtml {
    const raw = (value ?? '').trim();
    if (!raw) {
      return this.sanitizer.bypassSecurityTrustHtml('');
    }
    const html = marked(raw, { async: false }) as string;
    return this.sanitizer.bypassSecurityTrustHtml(html);
  }
}
